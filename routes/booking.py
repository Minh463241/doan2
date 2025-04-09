from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_supabase import get_available_rooms, insert_booking
from datetime import datetime

booking_bp = Blueprint('booking', __name__)

def tinh_tong_tien(ngay_nhan, ngay_tra, gia_phong):
    fmt = "%Y-%m-%d"
    d1 = datetime.strptime(ngay_nhan, fmt)
    d2 = datetime.strptime(ngay_tra, fmt)
    so_ngay = max((d2 - d1).days, 1)  # Tối thiểu 1 đêm
    return so_ngay * gia_phong

@booking_bp.route('/dat-phong', methods=['GET', 'POST'])
def dat_phong():
    if 'user' not in session:
        flash("Vui lòng đăng nhập trước khi đặt phòng.", "error")
        return redirect(url_for('auth.login'))

    customer = session.get('user')
    rooms = get_available_rooms()

    # Thiết lập mặc định cho các trường của phòng
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

            # Lấy giá phòng từ phòng được chọn
            phong_chon = next((room for room in rooms if str(room['maphong']) == str(maphong)), None)
            gia_phong = phong_chon['gia'] if phong_chon else 400000

            # Lấy ngày nhận và trả phòng từ form
            ngay_nhan = request.form['check_in']
            ngay_tra = request.form['check_out']

            # Tính tổng tiền
            tong_tien = tinh_tong_tien(ngay_nhan, ngay_tra, gia_phong)

            data = {
                "makhachhang": customer["id"],
                "maphong": int(maphong),
                "ngaynhanphong": ngay_nhan,
                "ngaytraphong": ngay_tra,
                "thoigiancheckindukien": request.form.get('expected_checkin_time'),
                "sokhachdicung": request.form.get('guest_info', ''),
                "ghichudatphong": request.form.get('note', ''),
                "songuoi": int(request.form.get('guests', 1)),
                "yeucaudacbiet": request.form.get('special_request', ''),
                "thoigiandat": datetime.now().isoformat(),
                "tongtien": tong_tien
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
