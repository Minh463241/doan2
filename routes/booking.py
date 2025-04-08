from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_supabase import get_available_rooms, insert_booking
from datetime import datetime

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/dat-phong', methods=['GET', 'POST'])
def dat_phong():
    if 'user' not in session:
        flash("Vui lòng đăng nhập trước khi đặt phòng.", "error")
        return redirect(url_for('auth.login'))

    customer = session.get('user')
    rooms = get_available_rooms()

    if request.method == 'POST':
        room_id = int(request.form['room_id'])
        check_in = datetime.fromisoformat(request.form['check_in'])
        check_out = datetime.fromisoformat(request.form['check_out'])

        # Tính số ngày
        so_ngay = (check_out - check_in).days
        if so_ngay <= 0:
            flash("Ngày trả phòng phải sau ngày nhận phòng.", "error")
            return redirect(url_for('booking.dat_phong'))

        # Lấy giá phòng từ danh sách phòng đã fetch ở trên
        gia_phong = next((room['giaphong'] for room in rooms if room['maphong'] == room_id), None)
        if gia_phong is None:
            flash("Không tìm thấy giá phòng!", "error")
            return redirect(url_for('booking.dat_phong'))

        # Tính tổng tiền
        tong_tien = so_ngay * gia_phong

        data = {
            "makhachhang": customer["id"],
            "maphong": room_id,
            "ngaynhanphong": check_in.isoformat(),
            "ngaytraphong": check_out.isoformat(),
            "songuoi": int(request.form['guests']),
            "yeucaudacbiet": request.form['special_request'],
            "thoigiandat": datetime.now().isoformat(),
            "tongtien": tong_tien  # ✅ Thêm dòng này
        }

        result = insert_booking(data)
        if result.data:
            flash("Đặt phòng thành công! Vui lòng thanh toán.", "success")
            return redirect(url_for('payment.pay', booking_id=result.data[0]['madatphong']))
        else:
            flash("Đặt phòng thất bại!", "error")

    return render_template("booking.html", rooms=rooms, customer=customer)
