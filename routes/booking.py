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
        room['loaiphong'] = room.get('loaiphong', f"Phòng {room['maphong']}")  # Dùng loaiphong
        room['hinhanh'] = room.get('hinhanh', 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?q=80&w=2070&auto=format&fit=crop')
        room['gia'] = room.get('giaphong', 400000)  # Dùng giaphong
        room['dientich'] = room.get('dientich', 30)
        room['succhua'] = room.get('succhua', 2)

    if request.method == 'POST':
        data = {
            "makhachhang": customer["id"],
            "maphong": int(request.form['room_id']),
            "ngaynhanphong": request.form['check_in'],
            "ngaytraphong": request.form['check_out'],
            "songuoi": int(request.form['guests']),
            "yeucaudacbiet": request.form['special_request'],
            "thoigiandat": datetime.now().isoformat()
        }
        result = insert_booking(data)
        if result.data:
            flash("Đặt phòng thành công! Vui lòng thanh toán.", "success")
            return redirect(url_for('payment.pay', booking_id=result.data[0]['madatphong']))
        else:
            flash("Đặt phòng thất bại!", "error")

    return render_template("booking.html", rooms=rooms, customer=customer)