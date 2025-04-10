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

        ngaynhanphong = datetime.strptime(ngaynhanphong, '%Y-%m-%d').date()
        ngaytraphong = datetime.strptime(ngaytraphong, '%Y-%m-%d').date()
        ngaydat = datetime.now().date()
        thoigiandat = datetime.now().isoformat()

        if ngaynhanphong >= ngaytraphong:
            flash('Ngày nhận phòng phải trước ngày trả phòng!', 'error')
            return redirect(url_for('booking.dat_phong'))

        room = supabase.table('phong').select('trangthai, succhua').eq('maphong', maphong).execute()
        if not room.data or room.data[0]['trangthai'] != 'Trống':
            flash('Phòng đã được đặt hoặc không tồn tại!', 'error')
            return redirect(url_for('booking.dat_phong'))

        if songuoi > room.data[0]['succhua']:
            flash(f'Phòng chỉ chứa tối đa {room.data[0]["succhua"]} người!', 'error')
            return redirect(url_for('booking.dat_phong'))

        # Lưu thông tin vào session tạm thời để dùng sau khi thanh toán
        session['datphong'] = {
            'makhachhang': session['user']['id'],
            'maphong': maphong,
            'ngaydat': ngaydat.isoformat(),
            'ngaynhanphong': ngaynhanphong.isoformat(),
            'ngaytraphong': ngaytraphong.isoformat(),
            'songuoi': songuoi,
            'tongtien': tongtien,
            'yeucaudacbiet': yeucaudacbiet,
            'thoigiancheckindukien': thoigiancheckindukien,
            'sokhachdicung': sokhachdicung,
            'ghichudatphong': ghichudatphong,
            'thoigiandat': thoigiandat
        }

        # Chuyển hướng sang PayPal
        return redirect(url_for('payment.pay'))

    # Nếu là GET, lấy danh sách phòng trống để hiển thị
    rooms_response = supabase.table('phong').select('*').eq('trangthai', 'Trống').execute()
    rooms = rooms_response.data
    return render_template('booking.html', rooms=rooms)


@booking_bp.route('/history')
def booking_history():
    # Kiểm tra nếu người dùng chưa đăng nhập
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    # Lấy ID người dùng đang đăng nhập (đây là khóa chính `makhachhang`)
    user_id = session['user']['id']  # hoặc session['user']['makhachhang']

    # Truy vấn lịch sử đặt phòng chỉ của người dùng này
    response = supabase.table('datphong')\
        .select('*')\
        .eq('makhachhang', user_id)\
        .order('ngaydat', desc=True)\
        .execute()

    history = response.data
    return render_template('booking/history.html', history=history)
