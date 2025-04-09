from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from supabase import create_client
from datetime import datetime

from config import Config

supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

# Khởi tạo Blueprint
booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/dat_phong', methods=['GET', 'POST'])
def dat_phong():
    if 'user' not in session:
        flash('Vui lòng đăng nhập để đặt phòng!', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        # Lấy dữ liệu từ form
        maphong = int(request.form.get('maphong'))
        ngaynhanphong = request.form.get('ngaynhanphong')
        ngaytraphong = request.form.get('ngaytraphong')
        songuoi = int(request.form.get('songuoi'))
        tongtien = float(request.form.get('tongtien'))
        yeucaudacbiet = request.form.get('yeucaudacbiet', '')
        thoigiancheckindukien = request.form.get('thoigiancheckindukien') or None
        sokhachdicung = request.form.get('sokhachdicung', '')
        ghichudatphong = request.form.get('ghichudatphong', '')

        # Chuyển đổi ngày thành định dạng datetime
        ngaynhanphong = datetime.strptime(ngaynhanphong, '%Y-%m-%d').date()
        ngaytraphong = datetime.strptime(ngaytraphong, '%Y-%m-%d').date()
        ngaydat = datetime.now().date()
        thoigiandat = datetime.now().isoformat()

        # Kiểm tra ngày hợp lệ
        if ngaynhanphong >= ngaytraphong:
            flash('Ngày nhận phòng phải trước ngày trả phòng!', 'error')
            return redirect(url_for('booking.dat_phong'))

        # Kiểm tra phòng có trống không
        room = supabase.table('phong').select('trangthai, succhua').eq('maphong', maphong).execute()
        if not room.data or room.data[0]['trangthai'] != 'available':
            flash('Phòng đã được đặt hoặc không tồn tại!', 'error')
            return redirect(url_for('booking.dat_phong'))

        # Kiểm tra số người có vượt quá sức chứa không
        if songuoi > room.data[0]['succhua']:
            flash(f'Phòng chỉ chứa tối đa {room.data[0]["succhua"]} người!', 'error')
            return redirect(url_for('booking.dat_phong'))

        # Lưu thông tin đặt phòng với trạng thái 'Chờ xác nhận'
        booking_data = {
            'makhachhang': session['user']['id'],
            'maphong': maphong,
            'ngaydat': ngaydat.isoformat(),
            'ngaynhanphong': ngaynhanphong.isoformat(),
            'ngaytraphong': ngaytraphong.isoformat(),
            'songuoi': songuoi,
            'trangthai': 'Chờ xác nhận',
            'tongtien': tongtien,
            'yeucaudacbiet': yeucaudacbiet,
            'thoigiancheckindukien': thoigiancheckindukien,
            'sokhachdicung': sokhachdicung,
            'ghichudatphong': ghichudatphong,
            'thoigiandat': thoigiandat
        }

        try:
            # Lưu đặt phòng
            supabase.table('datphong').insert(booking_data).execute()

            # Cập nhật trạng thái phòng thành 'booked' (tạm thời, chờ xác nhận)
            supabase.table('phong').update({'trangthai': 'booked'}).eq('maphong', maphong).execute()

            flash('Đặt phòng của bạn đã được ghi nhận, đang chờ xác nhận từ nhân viên!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            return redirect(url_for('booking.dat_phong'))

    # Nếu là GET, hiển thị form đặt phòng
    rooms = supabase.table('phong').select('*').eq('trangthai', 'available').execute().data
    return render_template('booking.html', rooms=rooms)