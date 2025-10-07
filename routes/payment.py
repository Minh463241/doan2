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
    update_room_status
)
import logging
import traceback

# ---- Logging ----
logging.basicConfig(level=logging.INFO, filename='payment.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

payment_bp = Blueprint('payment', __name__)

# ---- PayPal config ----
paypalrestsdk.configure({
    "mode": Config.PAYPAL_MODE,
    "client_id": Config.PAYPAL_CLIENT_ID,
    "client_secret": Config.PAYPAL_CLIENT_SECRET
})

# ---- Mapping enum ----
def map_trangthai_phong(status_vietnamese: str) -> str:
    mapping = {
        "Đã đặt": "da_dat",
        "Đang sử dụng": "dang_su_dung",
        "Trống": "trong",
        "Đã thanh toán": "dang_su_dung"  # Khi đặt phòng đã thanh toán thì phòng đang sử dụng
    }
    return mapping.get(status_vietnamese, status_vietnamese)



def map_trangthai_dichvu(status_vietnamese: str) -> str:
    mapping = {
        "Chưa thanh toán": "Chưa xử lý",
        "Chờ thanh toán": "Chưa xử lý",
        "Đã thanh toán": "Đã hoàn thành",
        "Đang phục vụ": "Đang xử lý"
    }
    return mapping.get(status_vietnamese, "Chưa xử lý") 



# ---- Session check ----
@payment_bp.before_request
def check_session():
    if request.endpoint not in ['payment.cancel'] and ('user' not in session or 'makhachhang' not in session.get('user', {})):
        flash("Vui lòng đăng nhập để tiếp tục!", "danger")
        logger.warning("Người dùng chưa đăng nhập, chuyển hướng đến trang login")
        return redirect(url_for('auth.login'))


# ---- Thanh toán ----
@payment_bp.route('/')
def pay():
    booking = session.get('booking')
    logger.info(f"Kiểm tra session booking: {booking}")
    if not booking or not all(k in booking for k in ['maphong', 'ngaynhanphong', 'ngaytraphong', 'tongtien', 'makhachhang', 'service_details']):
        flash("Thông tin đặt phòng không hợp lệ!", "danger")
        logger.error(f"Thông tin đặt phòng không hợp lệ trong session: {session.get('booking')}")
        return redirect(url_for('booking.dat_phong'))

    try:
        tongtien = float(booking['tongtien'])
        if tongtien <= 0:
            flash("Số tiền thanh toán không hợp lệ (phải lớn hơn 0)!", "danger")
            logger.error(f"Số tiền thanh toán không hợp lệ: tongtien={tongtien}")
            return redirect(url_for('booking.dat_phong'))

        exchange_rate = 25000
        amount_in_usd = tongtien / exchange_rate
        amount_str = f"{amount_in_usd:.2f}"
        if float(amount_str) < 0.01:
            flash("Số tiền sau khi chuyển đổi quá nhỏ (tối thiểu 0.01 USD)!", "danger")
            logger.error(f"Số tiền sau khi chuyển đổi nhỏ hơn 0.01 USD: amount_in_usd={amount_in_usd}")
            return redirect(url_for('booking.dat_phong'))

        logger.info(f"Thông tin thanh toán: maphong={booking['maphong']}, tongtien={tongtien} VNĐ, amount_in_usd={amount_str} USD")

        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {"total": amount_str, "currency": "USD"},
                "description": f"Thanh toán đặt phòng và dịch vụ cho phòng {booking['maphong']}",
                "custom": str(booking['maphong'])
            }],
            "redirect_urls": {
                "return_url": url_for('payment.success', _external=True),
                "cancel_url": url_for('payment.cancel', _external=True)
            }
        })

        if payment.create():
            approval_url = next(link.href for link in payment.links if link.rel == "approval_url")
            logger.info(f"Đã tạo giao dịch PayPal thành công, chuyển hướng đến: {approval_url}")
            return redirect(approval_url)
        else:
            logger.error(f"Lỗi tạo giao dịch PayPal: {payment.error}")
            error_message = payment.error.get('message', 'Lỗi không xác định')
            if 'details' in payment.error and isinstance(payment.error['details'], list):
                details = "; ".join(d['issue'] for d in payment.error['details'] if 'issue' in d)
                error_message += f" - Chi tiết: {details}"
            flash(f"Lỗi khi tạo giao dịch thanh toán: {error_message}", "danger")
            return redirect(url_for('booking.dat_phong'))

    except Exception as e:
        logger.error(f"Lỗi hệ thống khi tạo giao dịch: {e}\n{traceback.format_exc()}")
        flash("Lỗi hệ thống khi tạo giao dịch.", "danger")
        return redirect(url_for('booking.dat_phong'))


@payment_bp.route('/success')
def success():
    import unicodedata

    def _norm(s: str) -> str:
        try:
            return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
        except Exception:
            return (s or "").lower()

    def _safe_create_or_update_invoice_for_services(madatphong: int, makhachhang: int, amount: float, method: str, ngaylap: str):
        """Tạo hoặc cập nhật hóa đơn cộng dồn nếu đã tồn tại."""
        existing = supabase.from_("hoadon").select("mahoadon,tongtien").eq("madatphong", madatphong).execute().data or []
        if existing:
            ma = existing[0]["mahoadon"]
            old_total = float(existing[0].get("tongtien") or 0.0)
            new_total = old_total + float(amount)
            supabase.from_("hoadon").update({"tongtien": new_total}).eq("mahoadon", ma).execute()
            logger.info(f"[invoice] Updated mahoadon={ma}: {old_total} + {amount} => {new_total}")
            return

        # Chưa có → tạo mới
        # 2) Chưa có → tạo mới
        try:
            # Bảo vệ: nếu tổng tiền âm hoặc bằng 0, thì lấy trị tuyệt đối
            if float(amount) <= 0:
                logger.warning(f"[invoice] Tổng tiền âm ({amount}), tự động lấy giá trị tuyệt đối.")
                amount = abs(float(amount))

            update_booking_payment(madatphong, "Đã thanh toán")
            create_invoice(
                madatphong=madatphong,
                makhachhang=makhachhang,
                tongtien=float(amount),
                phuongthucthanhtoan=method,
                ngaylap=ngaylap
            )

            logger.info(f"[invoice] Created new invoice for madatphong={madatphong}, amount={amount}")
        except ValueError as ve:
            msg = _norm(str(ve))
            if "da ton tai" in msg or "đã tồn tại" in msg:
                logger.warning(f"[invoice] Exists, updating old one.")
                existing2 = supabase.from_("hoadon").select("mahoadon,tongtien").eq("madatphong", madatphong).execute().data or []
                if existing2:
                    ma = existing2[0]["mahoadon"]
                    old_total = float(existing2[0].get("tongtien") or 0.0)
                    new_total = old_total + float(amount)
                    supabase.from_("hoadon").update({"tongtien": new_total}).eq("mahoadon", ma).execute()
                    logger.info(f"[invoice] Updated mahoadon={ma}: {old_total}+{amount} => {new_total}")
            elif "chua duoc thanh toan" in msg or "chưa được thanh toán" in msg:
                logger.warning(f"[invoice] Bỏ qua tạo hóa đơn vì đơn chưa được đánh dấu thanh toán.")
            else:
                raise

    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    if not payment_id or not payer_id:
        msg = "Thiếu thông tin thanh toán!"
        flash(msg, "danger")
        logger.error("Thiếu paymentId hoặc PayerID")
        return render_template('payment_success.html', info=None, error=msg)

    try:
        payment = paypalrestsdk.Payment.find(payment_id)
        logger.info(f"Payment {payment_id} initial state={payment.state}")

        # Nếu chưa approved thì execute
        if payment.state != 'approved':
            executed = payment.execute({"payer_id": payer_id})
            if not executed:
                err = payment.error or {}
                err_name = err.get('name', '')
                err_msg = err.get('message', 'Lỗi không xác định khi execute.')
                if err_name not in ("PAYMENT_ALREADY_DONE", "INVALID_STATE"):
                    flash(f"Lỗi khi hoàn tất thanh toán: {err_msg}", "danger")
                    return render_template('payment_success.html', info=None, error=err_msg)
            payment = paypalrestsdk.Payment.find(payment_id)

        booking = session.pop('booking', None)
        required_keys = ['maphong', 'ngaynhanphong', 'ngaytraphong', 'tongtien', 'makhachhang', 'service_details']
        if not booking or not all(k in booking for k in required_keys):
            msg = "Không tìm thấy thông tin đặt phòng!"
            flash(msg, "danger")
            logger.error("Thiếu booking session sau khi thanh toán")
            return render_template('payment_success.html', info=None, error=msg)

        now = datetime.now()
        amount_total_usd = payment.transactions[0].amount.total
        amount_currency = payment.transactions[0].amount.currency
        payer_info = getattr(payment, 'payer', None) and getattr(payment.payer, 'payer_info', None)
        buyer_name = f"{getattr(payer_info, 'first_name', '')} {getattr(payer_info, 'last_name', '')}".strip() if payer_info else ''
        buyer_email = getattr(payer_info, 'email', '') if payer_info else ''

        # ====== TRƯỜNG HỢP: Mua thêm dịch vụ cho đơn đã có ======
        if booking.get('mode') == 'services_only' and booking.get('existing_booking_id'):
            madatphong = int(booking['existing_booking_id'])

            dp = supabase.from_("datphong").select("madatphong, trangthai").eq("madatphong", madatphong).single().execute().data
            if not dp:
                flash("Không tìm thấy đơn để ghi dịch vụ sau thanh toán.", "danger")
                return render_template('payment_success.html', info=None, error="Đơn không tồn tại.")

            if dp.get('trangthai') in {'Đã hủy', 'Đã trả phòng'}:
                msg = f"Đơn #{madatphong} đang “{dp.get('trangthai')}”, không thể ghi dịch vụ vào đơn."
                flash(msg, "danger")
                return render_template('payment_success.html', info=None, error=msg)

            # Ghi chi tiết dịch vụ
            for service in booking['service_details']:
                insert_service_usage({
                    'madatphong': madatphong,
                    'madichvu': service['madichvu'],
                    'soluong': int(service.get('soluong', 1)),
                    'thanhtien': float(service.get('thanhtien', 0.0)),
                    'trangthai': map_trangthai_dichvu('Đã thanh toán'),
                    'trangthaithanhtoan': 'Đã thanh toán',
                    'magiaodich': payment.id,
                    'ngaydat': now.isoformat()
                })

            # Cập nhật trạng thái & hóa đơn
            update_booking_payment(madatphong, "Đã thanh toán")
            _safe_create_or_update_invoice_for_services(
                madatphong=madatphong,
                makhachhang=booking['makhachhang'],
                amount=float(booking['tongtien']),
                method='PayPal',
                ngaylap=now.date().isoformat()
            )

            flash("Thanh toán dịch vụ thành công!", "success")
            return render_template('payment_success.html', info={
                'ma_don': payment.id,
                'ten_nguoi_mua': buyer_name,
                'email': buyer_email,
                'so_tien': amount_total_usd,
                'don_vi_tien': amount_currency
            })

        # ====== TRƯỜNG HỢP: Đặt phòng mới ======
        conflict = get_booking_by_room_date(booking['maphong'], booking['ngaynhanphong'], booking['ngaytraphong'])
        if conflict:
            msg = f"Phòng {booking['maphong']} đã được đặt trong khoảng thời gian này!"
            flash(msg, "danger")
            return render_template('payment_success.html', info=None, error=msg)

        datphong_data = {
            'makhachhang': booking['makhachhang'],
            'maphong': booking['maphong'],
            'ngaydat': now.date().isoformat(),
            'ngaynhanphong': booking['ngaynhanphong'],
            'ngaytraphong': booking['ngaytraphong'],
            'songuoi': booking.get('songuoi', 1),
            'trangthai': 'Đã thanh toán',
            'tongtien': float(booking['tongtien']),
            'yeucaudacbiet': booking.get('yeucaudacbiet', ''),
            'thoigiancheckindukien': booking.get('thoigiancheckindukien', ''),
            'sokhachdicung': str(booking.get('sokhachdicung', '0')),
            'ghichudatphong': booking.get('ghichudatphong', ''),
            'thoigiandat': now.isoformat(),
            'magiaodichpaypal': payment.id
        }

        logger.info(f"Insert booking (new): {datphong_data}")
        datphong_res = insert_booking(datphong_data)
        if not datphong_res or 'madatphong' not in datphong_res:
            flash("Lỗi khi lưu thông tin đặt phòng!", "danger")
            return render_template('payment_success.html', info=None, error="Lỗi khi lưu thông tin đặt phòng!")

        madatphong_new = int(datphong_res['madatphong'])

        # Cập nhật trạng thái phòng
        try:
            update_room_status(booking['maphong'], 'Đang sử dụng')
        except Exception as e_update:
            logger.warning(f"update_room_status failed: {e_update}", exc_info=True)

        # Ghi các dịch vụ đi kèm
        for service in booking['service_details']:
            insert_service_usage({
                'madatphong': madatphong_new,
                'madichvu': service['madichvu'],
                'soluong': int(service.get('soluong', 1)),
                'thanhtien': float(service.get('thanhtien', 0.0)),
                'trangthai': map_trangthai_dichvu('Đã thanh toán'),
                'trangthaithanhtoan': 'Đã thanh toán',
                'magiaodich': payment.id,
                'ngaydat': now.isoformat()
            })

        # --- Cập nhật trạng thái đặt phòng sang "Đã thanh toán" ---
        try:
            update_booking_payment(madatphong_new, "Đã thanh toán")
            logger.info(f"Đã cập nhật trạng thái đặt phòng {madatphong_new} -> Đã thanh toán")
        except Exception as e_update:
            logger.warning(f"Không thể cập nhật trạng thái đặt phòng {madatphong_new}: {e_update}", exc_info=True)

        # --- Tạo hóa đơn ---
        try:
            create_invoice(
                madatphong=madatphong_new,
                makhachhang=booking['makhachhang'],
                tongtien=float(booking['tongtien']),
                phuongthucthanhtoan='PayPal',
                ngaylap=now.date().isoformat()
            )
        except ValueError as ve:
            msg = _norm(str(ve))
            if "da ton tai" in msg or "đã tồn tại" in msg:
                logger.warning(f"[invoice] Duplicate for madatphong={madatphong_new}, skipped.")
            elif "chua duoc thanh toan" in msg or "chưa được thanh toán" in msg:
                logger.warning(f"[invoice] Bỏ qua tạo hóa đơn vì chưa cập nhật trạng thái: {ve}")
            else:
                logger.error(f"[invoice] create error: {ve}", exc_info=True)
                flash("Lỗi khi tạo hóa đơn.", "warning")

        flash("Thanh toán thành công! Đặt phòng và dịch vụ đã được xác nhận.", "success")
        return render_template('payment_success.html', info={
            'ma_don': payment.id,
            'ten_nguoi_mua': buyer_name,
            'email': buyer_email,
            'so_tien': amount_total_usd,
            'don_vi_tien': amount_currency
        })

    except paypalrestsdk.ResourceNotFound:
        msg = "Giao dịch không tồn tại hoặc đã hết hạn."
        flash(msg, "danger")
        logger.error(f"Payment not found: {payment_id}")
        return render_template('payment_success.html', info=None, error=msg)
    except Exception as e:
        msg = f"Lỗi hệ thống: {str(e)}"
        logger.error(f"/success exception: {str(e)}\n{traceback.format_exc()}")
        flash("Lỗi hệ thống khi xử lý thanh toán.", "danger")
        return render_template('payment_success.html', info=None, error=msg)


    
# ---- Hủy thanh toán ----
@payment_bp.route('/cancel')
def cancel():
    session.pop('booking', None)
    flash("Bạn đã hủy giao dịch thanh toán.", "warning")
    logger.info("Người dùng đã hủy giao dịch thanh toán")
    return redirect(url_for('booking.dat_phong'))
