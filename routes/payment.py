# routes/payment.py
from flask import Blueprint, flash, redirect, request, url_for, session, render_template
import paypalrestsdk
from datetime import datetime
from config import Config
from utils.db_supabase import (
    supabase,
    insert_booking,
    create_invoice,
    get_booking_by_room_date,
    update_booking_payment,
    insert_service_usage,
    update_room_status,
)
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import traceback

# =========================
# Logging an toàn cho serverless
# =========================
logger = logging.getLogger("payment")
if not logger.handlers:  # tránh nhân đôi handler khi warm start
    logger.setLevel(logging.INFO)
    if os.path.isdir("/tmp"):
        handler = RotatingFileHandler("/tmp/payment.log", maxBytes=5_000_000, backupCount=2)
    else:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

payment_bp = Blueprint("payment", __name__)

# =========================
# PayPal config
# =========================
paypalrestsdk.configure({
    "mode": Config.PAYPAL_MODE,
    "client_id": Config.PAYPAL_CLIENT_ID,
    "client_secret": Config.PAYPAL_CLIENT_SECRET,
})

# =========================
# Mapping (dịch vụ)
# =========================
def map_trangthai_dichvu(status_vietnamese: str) -> str:
    mapping = {
        "Chưa thanh toán": "Chưa xử lý",
        "Chờ thanh toán": "Chưa xử lý",
        "Đang phục vụ": "Đang xử lý",
        "Đã thanh toán": "Đã hoàn thành",
    }
    return mapping.get(status_vietnamese, "Chưa xử lý")

# =========================
# Session guard
# =========================
@payment_bp.before_request
def check_session():
    # Cho phép /cancel không cần login
    if request.endpoint in ('payment.cancel',):
        return
    user = session.get("user") or {}
    if "makhachhang" not in user:
        flash("Vui lòng đăng nhập để tiếp tục!", "danger")
        logger.warning("Người dùng chưa đăng nhập, chuyển hướng đến trang login")
        return redirect(url_for("auth.login"))

# =========================
# Khởi tạo thanh toán
# =========================
@payment_bp.route("/")
def pay():
    booking = session.get("booking")
    logger.info(f"Kiểm tra session booking: {booking}")

    required = {"maphong", "ngaynhanphong", "ngaytraphong", "tongtien", "makhachhang", "service_details"}
    if not booking or not required.issubset(booking.keys()):
        flash("Thông tin đặt phòng không hợp lệ!", "danger")
        logger.error(f"Thông tin booking không hợp lệ trong session: {session.get('booking')}")
        return redirect(url_for("booking.booking_page"))

    try:
        tongtien = float(booking["tongtien"])
        if tongtien <= 0:
            flash("Số tiền thanh toán không hợp lệ (phải > 0)!", "danger")
            logger.error(f"Số tiền không hợp lệ: {tongtien}")
            return redirect(url_for("booking.booking_page"))

        # Tỉ giá tạm
        exchange_rate = 25000
        amount_in_usd = tongtien / exchange_rate
        amount_str = f"{amount_in_usd:.2f}"
        if float(amount_str) < 0.01:
            flash("Số tiền sau quy đổi quá nhỏ (tối thiểu 0.01 USD)!", "danger")
            logger.error(f"Quy đổi < 0.01 USD: {amount_in_usd}")
            return redirect(url_for("booking.booking_page"))

        logger.info(f"Thanh toán: maphong={booking['maphong']}, VND={tongtien}, USD={amount_str}")

        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {"total": amount_str, "currency": "USD"},
                "description": f"Thanh toán đặt phòng và dịch vụ cho phòng {booking['maphong']}",
                "custom": str(booking["maphong"]),
            }],
            "redirect_urls": {
                "return_url": url_for("payment.success", _external=True),
                "cancel_url": url_for("payment.cancel", _external=True),
            },
        })

        if payment.create():
            approval_url = None
            for link in getattr(payment, "links", []):
                if getattr(link, "rel", "") == "approval_url":
                    approval_url = getattr(link, "href", None)
                    break
            if not approval_url:
                logger.error("Không tìm thấy approval_url trong response PayPal")
                flash("Không tạo được đường dẫn thanh toán PayPal.", "danger")
                return redirect(url_for("booking.booking_page"))
            logger.info(f"Tạo giao dịch PayPal OK, chuyển hướng: {approval_url}")
            return redirect(approval_url)
        else:
            logger.error(f"Lỗi tạo Payment: {payment.error}")
            error_message = (payment.error or {}).get("message", "Lỗi không xác định")
            details = (payment.error or {}).get("details", [])
            if isinstance(details, list) and details:
                joined = "; ".join(d.get("issue", "") for d in details if isinstance(d, dict))
                error_message += f" - {joined}"
            flash(f"Lỗi khi tạo giao dịch thanh toán: {error_message}", "danger")
            return redirect(url_for("booking.booking_page"))

    except Exception as e:
        logger.error(f"Lỗi hệ thống khi tạo giao dịch: {e}\n{traceback.format_exc()}")
        flash("Lỗi hệ thống khi tạo giao dịch.", "danger")
        return redirect(url_for("booking.booking_page"))

# =========================
# Hoàn tất thanh toán
# =========================
@payment_bp.route("/success")
def success():
    import unicodedata

    def _norm(s: str) -> str:
        try:
            return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
        except Exception:
            return (s or "").lower()

    def _safe_create_or_update_invoice_for_services(madatphong: int, makhachhang: int, amount: float, method: str, ngaylap: str, magiaodich: str):
        """Tạo mới hoặc cộng dồn hoá đơn nếu đã tồn tại."""
        existing = supabase.from_("hoadon").select("mahoadon,tongtien").eq("madatphong", madatphong).execute().data or []
        if existing:
            ma = existing[0]["mahoadon"]
            old_total = float(existing[0].get("tongtien") or 0.0)
            new_total = old_total + float(amount)
            supabase.from_("hoadon").update({"tongtien": new_total}).eq("mahoadon", ma).execute()
            logger.info(f"[invoice] Update mahoadon={ma}: {old_total} + {amount} => {new_total}")
            return

        # Chưa có -> tạo mới
        try:
            if float(amount) <= 0:
                logger.warning(f"[invoice] Tổng tiền âm/0 ({amount}), dùng trị tuyệt đối.")
                amount = abs(float(amount))

            # Đánh dấu booking đã thanh toán + lưu mã giao dịch
            update_booking_payment(madatphong, magiaodich)

            create_invoice(
                madatphong=madatphong,
                makhachhang=makhachhang,
                tongtien=float(amount),
                phuongthucthanhtoan=method,
                ngaylap=ngaylap,
            )
            logger.info(f"[invoice] Created for booking={madatphong}, amount={amount}")
        except ValueError as ve:
            msg = _norm(str(ve))
            if "da ton tai" in msg or "đã tồn tại" in msg:
                logger.warning("[invoice] Exists -> cộng dồn.")
                existing2 = supabase.from_("hoadon").select("mahoadon,tongtien").eq("madatphong", madatphong).execute().data or []
                if existing2:
                    ma = existing2[0]["mahoadon"]
                    old_total = float(existing2[0].get("tongtien") or 0.0)
                    new_total = old_total + float(amount)
                    supabase.from_("hoadon").update({"tongtien": new_total}).eq("mahoadon", ma).execute()
                    logger.info(f"[invoice] Update mahoadon={ma}: {old_total}+{amount} => {new_total}")
            elif "chua duoc thanh toan" in msg or "chưa được thanh toán" in msg:
                logger.warning("[invoice] Bỏ tạo hoá đơn vì đơn chưa đánh dấu thanh toán.")
            else:
                raise

    payment_id = request.args.get("paymentId")
    payer_id = request.args.get("PayerID")

    if not payment_id or not payer_id:
        msg = "Thiếu thông tin thanh toán!"
        flash(msg, "danger")
        logger.error("Thiếu paymentId hoặc PayerID")
        return render_template("payment_success.html", info=None, error=msg)

    try:
        payment = paypalrestsdk.Payment.find(payment_id)
        logger.info(f"Payment {payment_id} state={payment.state}")

        if payment.state != "approved":
            executed = payment.execute({"payer_id": payer_id})
            if not executed:
                err = payment.error or {}
                err_name = err.get("name", "")
                err_msg = err.get("message", "Lỗi không xác định khi execute.")
                if err_name not in ("PAYMENT_ALREADY_DONE", "INVALID_STATE"):
                    flash(f"Lỗi khi hoàn tất thanh toán: {err_msg}", "danger")
                    return render_template("payment_success.html", info=None, error=err_msg)
            payment = paypalrestsdk.Payment.find(payment_id)

        booking = session.pop("booking", None)
        required_keys = {"maphong", "ngaynhanphong", "ngaytraphong", "tongtien", "makhachhang", "service_details"}
        if not booking or not required_keys.issubset(booking.keys()):
            msg = "Không tìm thấy thông tin đặt phòng!"
            flash(msg, "danger")
            logger.error("Thiếu booking session sau thanh toán")
            return render_template("payment_success.html", info=None, error=msg)

        # Thông tin hiển thị
        now = datetime.now()
        transactions = getattr(payment, "transactions", [])
        amount_total_usd = amount_currency = ""
        if transactions:
            amount_total_usd = getattr(transactions[0].amount, "total", "")
            amount_currency = getattr(transactions[0].amount, "currency", "")
        payer_info = getattr(getattr(payment, "payer", None), "payer_info", None)
        buyer_name = f"{getattr(payer_info, 'first_name', '')} {getattr(payer_info, 'last_name', '')}".strip() if payer_info else ""
        buyer_email = getattr(payer_info, "email", "") if payer_info else ""
        magiaodich = payment.id

        # ====== TRƯỜNG HỢP: Chỉ mua dịch vụ thêm cho đơn đã có ======
        if booking.get("mode") == "services_only" and booking.get("existing_booking_id"):
            madatphong = int(booking["existing_booking_id"])

            dp = (supabase.from_("datphong")
                  .select("madatphong, trangthai")
                  .eq("madatphong", madatphong)
                  .single().execute().data)
            if not dp:
                flash("Không tìm thấy đơn để ghi dịch vụ sau thanh toán.", "danger")
                return render_template("payment_success.html", info=None, error="Đơn không tồn tại.")

            if dp.get("trangthai") in {"Đã hủy", "Đã trả phòng"}:
                msg = f"Đơn #{madatphong} đang “{dp.get('trangthai')}”, không thể ghi dịch vụ vào đơn."
                flash(msg, "danger")
                return render_template("payment_success.html", info=None, error=msg)

            # Ghi chi tiết dịch vụ
            for service in booking["service_details"]:
                insert_service_usage({
                    "madatphong": madatphong,
                    "madichvu": service["madichvu"],
                    "soluong": int(service.get("soluong", 1)),
                    "thanhtien": float(service.get("thanhtien", 0.0)),
                    "trangthai": map_trangthai_dichvu("Đã thanh toán"),
                    "trangthaithanhtoan": "Đã thanh toán",
                    "magiaodich": magiaodich,
                    "ngaydat": now.isoformat(),
                })

            # Cập nhật trạng thái & hoá đơn
            update_booking_payment(madatphong, magiaodich)
            _safe_create_or_update_invoice_for_services(
                madatphong=madatphong,
                makhachhang=booking["makhachhang"],
                amount=float(booking["tongtien"]),
                method="PayPal",
                ngaylap=now.date().isoformat(),
                magiaodich=magiaodich,
            )

            flash("Thanh toán dịch vụ thành công!", "success")
            return render_template("payment_success.html", info={
                "ma_don": magiaodich,
                "ten_nguoi_mua": buyer_name,
                "email": buyer_email,
                "so_tien": amount_total_usd,
                "don_vi_tien": amount_currency,
            })

        # ====== TRƯỜNG HỢP: Đặt phòng mới ======
        conflict = get_booking_by_room_date(booking["maphong"], booking["ngaynhanphong"], booking["ngaytraphong"])
        if conflict:
            msg = f"Phòng {booking['maphong']} đã được đặt trong khoảng thời gian này!"
            flash(msg, "danger")
            return render_template("payment_success.html", info=None, error=msg)

        datphong_data = {
            "makhachhang": booking["makhachhang"],
            "maphong": booking["maphong"],
            "ngaydat": now.date().isoformat(),
            "ngaynhanphong": booking["ngaynhanphong"],
            "ngaytraphong": booking["ngaytraphong"],
            "songuoi": booking.get("songuoi", 1),
            "trangthai": "Đã thanh toán",
            "tongtien": float(booking["tongtien"]),
            "yeucaudacbiet": booking.get("yeucaudacbiet", ""),
            "thoigiancheckindukien": booking.get("thoigiancheckindukien", ""),
            "sokhachdicung": str(booking.get("sokhachdicung", "0")),
            "ghichudatphong": booking.get("ghichudatphong", ""),
            "thoigiandat": now.isoformat(),
            "magiaodichpaypal": magiaodich,
        }

        logger.info(f"Insert booking (new): {datphong_data}")
        datphong_res = insert_booking(datphong_data)
        if not datphong_res or "madatphong" not in datphong_res:
            msg = "Lỗi khi lưu thông tin đặt phòng!"
            flash(msg, "danger")
            return render_template("payment_success.html", info=None, error=msg)

        madatphong_new = int(datphong_res["madatphong"])

        # Cập nhật trạng thái phòng
        try:
            update_room_status(booking["maphong"], "Đang sử dụng")  # mapping enum ở utils
        except Exception as e_update:
            logger.warning(f"update_room_status failed: {e_update}", exc_info=True)

        # Ghi các dịch vụ đi kèm
        for service in booking["service_details"]:
            insert_service_usage({
                "madatphong": madatphong_new,
                "madichvu": service["madichvu"],
                "soluong": int(service.get("soluong", 1)),
                "thanhtien": float(service.get("thanhtien", 0.0)),
                "trangthai": map_trangthai_dichvu("Đã thanh toán"),
                "trangthaithanhtoan": "Đã thanh toán",
                "magiaodich": magiaodich,
                "ngaydat": now.isoformat(),
            })

        # Đánh dấu đặt phòng đã thanh toán + lưu mã giao dịch
        try:
            update_booking_payment(madatphong_new, magiaodich)
            logger.info(f"Đã cập nhật trạng thái đặt phòng {madatphong_new} -> Đã thanh toán")
        except Exception as e_update:
            logger.warning(f"Không thể cập nhật trạng thái đặt phòng {madatphong_new}: {e_update}", exc_info=True)

        # Tạo hoá đơn
        try:
            create_invoice(
                madatphong=madatphong_new,
                makhachhang=booking["makhachhang"],
                tongtien=float(booking["tongtien"]),
                phuongthucthanhtoan="PayPal",
                ngaylap=now.date().isoformat(),
            )
        except ValueError as ve:
            msg = _norm(str(ve))
            if "da ton tai" in msg or "đã tồn tại" in msg:
                logger.warning(f"[invoice] Duplicate for madatphong={madatphong_new}, skipped.")
            elif "chua duoc thanh toan" in msg or "chưa được thanh toán" in msg:
                logger.warning(f"[invoice] Bỏ tạo hoá đơn vì chưa cập nhật trạng thái: {ve}")
            else:
                logger.error(f"[invoice] create error: {ve}", exc_info=True)
                flash("Lỗi khi tạo hoá đơn.", "warning")

        flash("Thanh toán thành công! Đặt phòng và dịch vụ đã được xác nhận.", "success")
        return render_template("payment_success.html", info={
            "ma_don": magiaodich,
            "ten_nguoi_mua": buyer_name,
            "email": buyer_email,
            "so_tien": amount_total_usd,
            "don_vi_tien": amount_currency,
        })

    except paypalrestsdk.ResourceNotFound:
        msg = "Giao dịch không tồn tại hoặc đã hết hạn."
        flash(msg, "danger")
        logger.error(f"Payment not found: {payment_id}")
        return render_template("payment_success.html", info=None, error=msg)
    except Exception as e:
        msg = f"Lỗi hệ thống: {str(e)}"
        logger.error(f"/success exception: {str(e)}\n{traceback.format_exc()}")
        flash("Lỗi hệ thống khi xử lý thanh toán.", "danger")
        return render_template("payment_success.html", info=None, error=msg)

# =========================
# Huỷ thanh toán
# =========================
@payment_bp.route("/cancel")
def cancel():
    session.pop("booking", None)
    flash("Bạn đã hủy giao dịch thanh toán.", "warning")
    logger.info("Người dùng đã hủy giao dịch thanh toán")
    return redirect(url_for("booking.booking_page"))
