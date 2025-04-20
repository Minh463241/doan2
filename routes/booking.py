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
            'makhachhang': session['user']['makhachhang'],
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
        flash('Vui lòng đăng nhập để xem lịch sử đặt phòng!', 'error')
        return redirect(url_for('auth.login'))

    # Kiểm tra xem session['user'] có khóa 'makhachhang' không
    if 'makhachhang' not in session['user']:
        flash('Không tìm thấy thông tin người dùng. Vui lòng đăng nhập lại.', 'error')
        return redirect(url_for('auth.login'))

    # Lấy ID người dùng đang đăng nhập
    user_id = session['user']['makhachhang']

    # Truy vấn lịch sử đặt phòng chỉ của người dùng này
    response = supabase.table('datphong')\
        .select('*')\
        .eq('makhachhang', user_id)\
        .order('ngaydat', desc=True)\
        .execute()

    history = response.data
    return render_template('booking/history.html', history=history)

@booking_bp.route('/order_service/<int:madatphong>', methods=['GET', 'POST'])
def order_service(madatphong):
    # Kiểm tra nếu người dùng chưa đăng nhập
    if 'user' not in session:
        flash('Vui lòng đăng nhập để đặt dịch vụ!', 'error')
        return redirect(url_for('auth.login'))

    # Lấy thông tin đặt phòng dựa trên madatphong
    booking = supabase.table('datphong').select('*').eq('madatphong', madatphong).execute()
    if not booking.data:
        flash('Không tìm thấy thông tin đặt phòng!', 'error')
        return redirect(url_for('booking.history'))

    # Kiểm tra xem đặt phòng có thuộc về người dùng hiện tại không
    if booking.data[0]['makhachhang'] != session['user']['makhachhang']:
        flash('Bạn không có quyền truy cập đặt phòng này!', 'error')
        return redirect(url_for('booking.history'))

    # Lấy danh sách dịch vụ đã đặt cho đặt phòng này
    services = supabase.table('chitietdichvu')\
        .select('madichvu, soluong')\
        .eq('madatphong', madatphong)\
        .execute()

    # Lấy thông tin chi tiết của các dịch vụ (tên, giá, v.v.)
    services_data = []
    if services.data:
        for s in services.data:
            dichvu = supabase.table('dichvu')\
                .select('tendichvu, giadichvu')\
                .eq('madichvu', s['madichvu'])\
                .execute()
            if dichvu.data:
                services_data.append({
                    'tendichvu': dichvu.data[0]['tendichvu'],
                    'soluong': s['soluong'],
                    'giadichvu': dichvu.data[0]['giadichvu'],
                    'thanhtien': s['soluong'] * dichvu.data[0]['giadichvu']
                })

    # Lấy danh sách tất cả dịch vụ có sẵn để hiển thị trong form
    dichvus = supabase.table('dichvu').select('madichvu, tendichvu, giadichvu').execute()

    if request.method == 'POST':
        # Lấy dữ liệu từ form
        madichvu = int(request.form.get('madichvu'))
        soluong = int(request.form.get('soluong'))

        # Kiểm tra xem dịch vụ đã được đặt trước đó chưa
        existing_service = supabase.table('chitietdichvu')\
            .select('soluong')\
            .eq('madatphong', madatphong)\
            .eq('madichvu', madichvu)\
            .execute()

        if existing_service.data:
            # Nếu dịch vụ đã được đặt, cập nhật số lượng
            new_soluong = existing_service.data[0]['soluong'] + soluong
            supabase.table('chitietdichvu')\
                .update({'soluong': new_soluong})\
                .eq('madatphong', madatphong)\
                .eq('madichvu', madichvu)\
                .execute()
        else:
            # Nếu chưa có, thêm mới vào bảng chitietdichvu
            supabase.table('chitietdichvu')\
                .insert({
                    'madatphong': madatphong,
                    'madichvu': madichvu,
                    'soluong': soluong
                })\
                .execute()

        flash('Đặt dịch vụ thành công!', 'success')
        return redirect(url_for('booking.order_service', madatphong=madatphong))

    # Nếu là GET, hiển thị form để đặt dịch vụ
    return render_template('booking/order_service.html', madatphong=madatphong, services=services_data, dichvus=dichvus.data)