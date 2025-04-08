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

    # Đảm bảo dữ liệu phòng có các trường cần thiết
    for room in rooms:
        room['loaiphong'] = room.get('loaiphong', f"Phòng {room['maphong']}")
        room['hinhanh'] = room.get('hinhanh', 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?q=80&w=2070&auto=format&fit=crop')
        room['gia'] = room.get('giaphong', 400000)
        room['dientich'] = room.get('dientich', 30)
        room['succhua'] = room.get('succhua', 2)

    if request.method == 'POST':
        try:
            maphong = request.form.get('room_id')
            if not maphong:
                flash("Vui lòng chọn phòng trước khi đặt.", "error")
                return redirect(url_for('booking.dat_phong'))

            data = {
                "makhachhang": customer["id"],
                "maphong": int(maphong),
                "ngaynhanphong": request.form['check_in'],
                "ngaytraphong": request.form['check_out'],
                "thoigiancheckindukien": request.form.get('expected_checkin_time'),
                "sokhachdicung": request.form.get('guest_info', ''),
                "ghichudatphong": request.form.get('note', ''),
                "songuoi": int(request.form.get('guests', 1)),
                "yeucaudacbiet": request.form.get('special_request', ''),
                "thoigiandat": datetime.now().isoformat()
            }

            result = insert_booking(data)
            if result.data:
                flash("Đặt phòng thành công! Vui lòng thanh toán.", "success")
                return redirect(url_for('payment.pay', booking_id=result.data[0]['madatphong']))
            else:
                flash("Đặt phòng thất bại!", "error")
        
        except Exception as e:
            flash(f"Lỗi khi đặt phòng: {e}", "danger")

    return render_template("booking.html", rooms=rooms, customer=customer)
