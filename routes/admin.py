from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from supabase import create_client
from config import Config
from utils.db_supabase import get_admin_by_email

supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        admin = get_admin_by_email(email)

        if admin:
            # So sánh trực tiếp với mật khẩu lưu trong CSDL (không mã hóa)
            if admin.get("matkhau") == password:
                session['admin'] = {'email': admin['email']}
                flash('Đăng nhập admin thành công!', 'success')
                return redirect(url_for('admin.confirm_booking'))

        flash('Email hoặc mật khẩu không đúng!', 'error')

    return render_template('admin/admin_login.html')


@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Đã đăng xuất khỏi admin!', 'success')
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/confirm-booking', methods=['GET', 'POST'])
def confirm_booking():
    if 'admin' not in session:
        flash('Bạn không có quyền truy cập!', 'error')
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        madatphong = int(request.form.get('madatphong'))
        action = request.form.get('action')

        booking = supabase.table('datphong').select('maphong, trangthai').eq('madatphong', madatphong).execute()
        if not booking.data:
            flash('Đặt phòng không tồn tại!', 'error')
            return redirect(url_for('admin.confirm_booking'))

        maphong = booking.data[0]['maphong']

        if action == 'confirm':
            supabase.table('datphong').update({'trangthai': 'Đã xác nhận'}).eq('madatphong', madatphong).execute()
            flash(f'Đã xác nhận đặt phòng #{madatphong}!', 'success')
        elif action == 'reject':
            supabase.table('datphong').update({'trangthai': 'Đã hủy'}).eq('madatphong', madatphong).execute()
            supabase.table('phong').update({'trangthai': 'available'}).eq('maphong', maphong).execute()
            flash(f'Đã từ chối đặt phòng #{madatphong}!', 'success')

        return redirect(url_for('admin.confirm_booking'))

    bookings = supabase.table('datphong').select('*').eq('trangthai', 'Chờ xác nhận').execute().data
    return render_template('admin/confirm_booking.html', bookings=bookings)
