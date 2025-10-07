# routes/booking.py
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from utils.db_supabase import (
    supabase,                 # Đảm bảo import đối tượng supabase
    get_available_rooms,
    get_all_services,
    insert_booking,
    insert_service_usage,
    create_invoice,
    get_customer_by_id,
    update_room_status,
)

# =========================
# Logging an toàn cho serverless
# =========================
logger = logging.getLogger("booking")
if not logger.handlers:  # tránh nhân đôi handler khi module được import nhiều lần (Lambda warm start)
    logger.setLevel(logging.INFO)
    if os.path.isdir("/tmp"):
        log_path = os.path.join("/tmp", "booking.log")
        handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=2)
    else:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

booking_bp = Blueprint("booking", __name__)

# =========================
# GET: Trang đặt phòng
# =========================
@booking_bp.route("/dat_phong", methods=["GET"])
def booking_page():
    """Hiển thị trang đặt phòng với danh sách phòng trống và dịch vụ."""
    today = datetime.now().date().isoformat()
    try:
        ngaynhanphong = request.args.get("ngaynhanphong", "")
        ngaytraphong = request.args.get("ngaynhanphong", "")  # default nhầm?
        ngaytraphong = request.args.get("ngaytraphong", ngaytraphong)

        if ngaynhanphong and ngaytraphong:
            try:
                checkin_date = datetime.fromisoformat(ngaynhanphong).date()
                checkout_date = datetime.fromisoformat(ngaytraphong).date()

                if checkin_date < datetime.now().date():
                    flash("Ngày nhận phòng không được trước ngày hiện tại.", "danger")
                    ngaynhanphong = today
                    ngaytraphong = ""
                elif checkin_date >= checkout_date:
                    flash("Ngày trả phòng phải sau ngày nhận phòng.", "danger")
                    ngaytraphong = ""
            except ValueError:
                flash("Định dạng ngày không hợp lệ.", "danger")
                ngaynhanphong = today
                ngaytraphong = ""
        else:
            # Mặc định hôm nay, chưa chọn ngày trả
            ngaynhanphong = today
            ngaytraphong = ""

        # Lấy phòng & dịch vụ
        rooms = get_available_rooms(ngaynhanphong, ngaytraphong) if ngaytraphong else get_available_rooms(None, None)
        services = get_all_services()

        logger.info(f"Trang đặt phòng: rooms={len(rooms)} services={len(services)}")
        return render_template(
            "booking.html",
            rooms=rooms,
            services=services,
            ngaynhanphong=ngaynhanphong,
            ngaytraphong=ngaytraphong,
        )
    except Exception as e:
        logger.error(f"Lỗi khi hiển thị trang đặt phòng: {str(e)}", exc_info=True)
        flash("Đã xảy ra lỗi khi tải trang đặt phòng. Vui lòng thử lại.", "danger")
        # fallback an toàn
        return render_template("booking.html", rooms=[], services=[], ngaynhanphong=today, ngaytraphong="")

# =========================
# GET: Lọc phòng (tách route để tránh đụng độ)
# =========================
@booking_bp.route("/dat_phong/filter", methods=["GET"])
def dat_phong_filter():
    try:
        ngaynhanphong = request.args.get("ngaynhanphong")
        ngaytraphong = request.args.get("ngaytraphong")

        if not ngaynhanphong or not ngaytraphong:
            flash("Vui lòng chọn ngày nhận và trả phòng!", "warning")
            return redirect(url_for("booking.booking_page"))

        # Dùng API đúng để lấy danh sách phòng trống
        rooms = get_available_rooms(ngaynhanphong, ngaytraphong) or []
        logger.info(f"Lọc phòng trống: {ngaynhanphong} -> {ngaytraphong}, rooms={len(rooms)}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(rooms)

        # Render lại trang booking với dữ liệu đã lọc
        services = get_all_services()
        return render_template(
            "booking.html",
            rooms=rooms,
            services=services,
            ngaynhanphong=ngaynhanphong,
            ngaytraphong=ngaytraphong,
        )
    except Exception as e:
        logger.error(f"Lỗi khi lọc phòng: {str(e)}", exc_info=True)
        flash("Không thể tải danh sách phòng, vui lòng thử lại.", "danger")
        return redirect(url_for("booking.booking_page"))

# =========================
# POST: Xử lý đặt phòng
# =========================
@booking_bp.route("/dat_phong", methods=["POST"])
def dat_phong():
    """Xử lý đặt phòng và dịch vụ từ form, chuyển hướng đến thanh toán."""
    try:
        logger.info(f"Nhận yêu cầu đặt phòng với session: {session.get('user')}")
        if not session.get("user") or not session["user"].get("makhachhang"):
            logger.warning("Người dùng chưa đăng nhập hoặc thiếu makhachhang")
            flash("Vui lòng đăng nhập để đặt phòng.", "danger")
            return redirect(url_for("auth.login"))

        makhachhang = session["user"]["makhachhang"]
        customer = get_customer_by_id(makhachhang)
        if not customer:
            flash("Không tìm thấy thông tin khách hàng.", "danger")
            return redirect(url_for("auth.login"))

        # Lấy dữ liệu form
        maphong = request.form.get("maphong")
        giaphong = float(request.form.get("giaphong", 0))
        ngaynhanphong = request.form.get("ngaynhanphong")
        ngaytraphong = request.form.get("ngaytraphong")
        songuoi = int(request.form.get("songuoi", 0))
        thoigiancheckindukien = request.form.get("thoigiancheckindukien", None)
        yeucaudacbiet = request.form.get("yeucaudacbiet", "")
        sokhachdicung = request.form.get("sokhachdicung", "0")
        ghichudatphong = request.form.get("ghichudatphong", "")
        services = request.form.getlist("services")

        today_date = datetime.now().date()
        checkin_date = datetime.fromisoformat(ngaynhanphong).date()
        checkout_date = datetime.fromisoformat(ngaytraphong).date()
        nights = max(1, (checkout_date - checkin_date).days)  # luôn >= 1

        # Validate cơ bản
        if checkin_date < today_date:
            flash("Ngày nhận phòng không được trước ngày hiện tại.", "danger")
            return redirect(url_for("booking.booking_page"))
        if nights < 1:
            flash("Thời gian đặt phải ít nhất 1 ngày.", "danger")
            return redirect(url_for("booking.booking_page"))
        if songuoi <= 0:
            flash("Số người phải lớn hơn 0.", "danger")
            return redirect(url_for("booking.booking_page"))
        if giaphong <= 0:
            flash("Giá phòng không hợp lệ.", "danger")
            return redirect(url_for("booking.booking_page"))

        # Validate thời gian check-in
        if thoigiancheckindukien:
            try:
                checkin_time = datetime.fromisoformat(thoigiancheckindukien.replace("Z", "+00:00"))
                if checkin_time.date() != checkin_date:
                    flash("Thời gian check-in phải trong ngày nhận phòng.", "danger")
                    return redirect(url_for("booking.booking_page"))
            except ValueError:
                flash("Thời gian check-in không hợp lệ.", "danger")
                return redirect(url_for("booking.booking_page"))

        # Tính tiền phòng
        room_cost = giaphong * nights

        # Tính tiền dịch vụ
        service_details = []
        service_cost = 0.0
        all_services = get_all_services()
        for madichvu in services:
            quantity = int(request.form.get(f"quantity_{madichvu}", 0))
            if quantity <= 0:
                flash(f"Số lượng cho dịch vụ {madichvu} phải lớn hơn 0.", "danger")
                return redirect(url_for("booking.booking_page"))
            service = next((s for s in all_services if str(s["madichvu"]) == madichvu), None)
            if not service:
                flash(f"Dịch vụ {madichvu} không tồn tại.", "danger")
                return redirect(url_for("booking.booking_page"))
            line = float(service["giadichvu"]) * quantity
            service_cost += line
            service_details.append({
                "madichvu": madichvu,
                "soluong": quantity,
                "thanhtien": line,
                "trangthai": "Chờ thanh toán",
            })

        total_cost = room_cost + service_cost
        if total_cost <= 0:
            flash("Tổng số tiền không hợp lệ.", "danger")
            return redirect(url_for("booking.booking_page"))

        # Lưu vào session để chuyển sang thanh toán
        booking_data = {
            "makhachhang": makhachhang,
            "maphong": maphong,
            "ngaynhanphong": ngaynhanphong,
            "ngaytraphong": ngaytraphong,
            "tongtien": total_cost,
            "songuoi": songuoi,
            "thoigiancheckindukien": thoigiancheckindukien,
            "yeucaudacbiet": yeucaudacbiet,
            "sokhachdicung": sokhachdicung,
            "ghichudatphong": ghichudatphong,
            "service_details": service_details,
        }
        session["booking"] = booking_data
        logger.info(f"Chuyển hướng sang thanh toán với booking_data: {booking_data}")

        return redirect(url_for("payment.pay"))

    except Exception as e:
        logger.error(f"Lỗi khi đặt phòng: {str(e)}", exc_info=True)
        flash("Đã xảy ra lỗi khi đặt phòng. Vui lòng thử lại.", "danger")
        return redirect(url_for("booking.booking_page"))

# =========================
# GET: Lịch sử đặt phòng
# =========================
@booking_bp.route("/booking_history")
def booking_history():
    """Hiển thị lịch sử đặt phòng của khách hàng."""
    try:
        logger.info(f"Session user: {session.get('user')}")
        if not session.get("user") or not session.get("user").get("makhachhang"):
            flash("Vui lòng đăng nhập để xem lịch sử đặt phòng.", "danger")
            return redirect(url_for("auth.login"))

        makhachhang = session["user"]["makhachhang"]
        logger.info(f"makhachhang: {makhachhang}")
        bookings = (
            supabase
            .from_("datphong")
            .select("*, phong(loaiphong)")
            .eq("makhachhang", makhachhang)
            .execute()
            .data or []
        )
        for booking in bookings:
            services = (
                supabase
                .from_("chitietdichvu")
                .select("*, dichvu(tendichvu)")
                .eq("madatphong", booking["madatphong"])
                .execute()
                .data or []
            )
            booking["services"] = services

        logger.info(f"Hiển thị lịch sử đặt phòng cho {makhachhang}: {len(bookings)} đơn")
        return render_template("booking/booking_history.html", bookings=bookings)
    except Exception as e:
        logger.error(f"Lỗi khi hiển thị lịch sử đặt phòng: {str(e)}", exc_info=True)
        flash("Đã xảy ra lỗi khi tải lịch sử đặt phòng. Vui lòng thử lại.", "danger")
        return render_template("booking/booking_history.html", bookings=[])

# =========================
# GET: Xem chi tiết đặt phòng
# =========================
@booking_bp.route("/booking/<int:madatphong>", methods=["GET"])
def view_detail(madatphong):
    """Trang chi tiết đặt phòng + form đặt thêm dịch vụ."""
    try:
        # Bắt buộc đăng nhập
        if not session.get("user") or not session["user"].get("makhachhang"):
            flash("Vui lòng đăng nhập để xem chi tiết đặt phòng.", "danger")
            return redirect(url_for("auth.login"))

        # Lấy đơn đặt phòng
        booking = (
            supabase
            .from_("datphong")
            .select("*, phong(loaiphong)")
            .eq("madatphong", madatphong)
            .single()
            .execute()
            .data
        )
        if not booking:
            flash("Không tìm thấy đơn đặt phòng.", "danger")
            return redirect(url_for("booking.booking_history"))

        # Lấy danh sách dịch vụ đã đặt cho đơn này
        services_used = (
            supabase
            .from_("chitietdichvu")
            .select("*, dichvu(tendichvu, giadichvu)")
            .eq("madatphong", madatphong)
            .execute()
            .data or []
        )
        booking["services"] = services_used

        # Lấy tất cả dịch vụ (để render form)
        all_services = get_all_services()

        return render_template(
            "booking/booking_detail.html",
            booking=booking,
            all_services=all_services,
        )
    except Exception as e:
        logger.error(f"Lỗi view_detail: {e}", exc_info=True)
        flash("Có lỗi khi tải chi tiết đặt phòng.", "danger")
        return redirect(url_for("booking.booking_history"))

# =========================
# POST: Đặt thêm dịch vụ cho một booking
# =========================
@booking_bp.route("/<int:madatphong>/add-service", methods=["POST"], endpoint="add_service")
def add_service(madatphong):
    try:
        # --- Kiểm tra đăng nhập ---
        if not session.get("user") or not session["user"].get("makhachhang"):
            flash("Vui lòng đăng nhập để đặt dịch vụ.", "danger")
            return redirect(url_for("auth.login"))

        # --- Lấy thông tin đơn đặt phòng ---
        booking_db = (
            supabase.from_("datphong")
            .select("madatphong, maphong, ngaynhanphong, ngaytraphong, songuoi, tongtien, trangthai")
            .eq("madatphong", madatphong)
            .single()
            .execute()
            .data
        )
        if not booking_db:
            flash("Không tìm thấy đơn đặt phòng.", "danger")
            return redirect(url_for("booking.booking_history"))

        if booking_db.get("trangthai") in {"Đã hủy", "Đã trả phòng"}:
            flash(f"Đơn #{madatphong} đang ở trạng thái “{booking_db.get('trangthai')}”, không thể thêm dịch vụ.", "danger")
            return redirect(url_for("booking.view_detail", madatphong=madatphong))

        # --- Lấy danh sách dịch vụ người dùng chọn ---
        service_ids = request.form.getlist("service_id[]") or request.form.getlist("service_id")
        quantities = request.form.getlist("quantity[]") or [request.form.get("quantity")]
        if not service_ids or not quantities or len(service_ids) != len(quantities):
            flash("Vui lòng chọn ít nhất một dịch vụ hợp lệ.", "danger")
            return redirect(url_for("booking.view_detail", madatphong=madatphong))

        # --- Lấy danh sách dịch vụ từ DB ---
        all_services_list = get_all_services()
        all_services = {str(s["madichvu"]): s for s in all_services_list}

        service_details = []
        service_cost = 0.0

        for sid, qty in zip(service_ids, quantities):
            if not sid:
                continue
            try:
                qty = int(qty or 0)
            except ValueError:
                qty = 0
            if qty <= 0:
                flash("Số lượng dịch vụ phải lớn hơn 0.", "danger")
                return redirect(url_for("booking.view_detail", madatphong=madatphong))

            if str(sid) not in all_services:
                flash(f"Dịch vụ {sid} không tồn tại.", "danger")
                return redirect(url_for("booking.view_detail", madatphong=madatphong))

            dv = all_services[str(sid)]
            try:
                gia_dv = float(dv["giadichvu"])
            except (ValueError, TypeError):
                gia_dv = 0.0
            if gia_dv <= 0:
                logger.warning(f"Dịch vụ {dv.get('tendichvu', sid)} có giá không hợp lệ ({dv.get('giadichvu')})")
                flash(f"Dịch vụ {dv.get('tendichvu', sid)} có giá không hợp lệ.", "danger")
                return redirect(url_for("booking.view_detail", madatphong=madatphong))

            line_total = gia_dv * qty
            service_cost += line_total
            service_details.append({
                "madichvu": int(sid),
                "soluong": qty,
                "thanhtien": line_total,
            })

        if service_cost <= 0:
            logger.warning(f"[add_service] Tổng tiền dịch vụ = {service_cost}, tự động lấy trị tuyệt đối.")
            service_cost = abs(service_cost)

        # --- Lưu thông tin vào session để chuyển sang PayPal ---
        session["booking"] = {
            "mode": "services_only",
            "existing_booking_id": madatphong,
            "makhachhang": session["user"]["makhachhang"],
            "maphong": booking_db["maphong"],
            "ngaynhanphong": booking_db["ngaynhanphong"],
            "ngaytraphong": booking_db["ngaytraphong"],
            "songuoi": booking_db.get("songuoi", 1),
            "tongtien": service_cost,
            "service_details": service_details,
            "yeucaudacbiet": "",
            "thoigiancheckindukien": "",
            "sokhachdicung": "0",
            "ghichudatphong": "",
        }

        logger.info(f"[add_service] Chuẩn bị thanh toán cho đơn #{madatphong} với tổng dịch vụ = {service_cost}")
        return redirect(url_for("payment.pay"))

    except Exception as e:
        logger.error(f"Lỗi add_service: {e}", exc_info=True)
        flash("Có lỗi khi chuyển sang thanh toán. Vui lòng thử lại.", "danger")
        return redirect(url_for("booking.view_detail", madatphong=madatphong))
