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
                # Lấy quyền từ trường 'chucvu' và chuyển về dạng lowercase
                role = admin.get("chucvu", "").lower()
                # Lưu thông tin người dùng vào session
                session['user'] = {'email': admin['email'], 'role': role}
                flash('Đăng nhập thành công!', 'success')
                # Điều hướng theo role:
                if role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif role == 'manager':
                    return redirect(url_for('manager.dashboard'))
                elif role == 'nhanvien':
                    # Nếu là nhân viên thì chuyển tới chức năng confirm_booking
                    return redirect(url_for('employee.confirm_booking'))
                else:
                    flash('Quyền của bạn không được hỗ trợ!', 'error')
                    return redirect(url_for('admin.admin_login'))
            else:
                flash('Mật khẩu không đúng!', 'error')
        else:
            flash('Email không tồn tại!', 'error')

    return render_template('admin/admin_login.html')


@admin_bp.route('/logout')
def admin_logout():
    session.pop('user', None)
    flash('Đã đăng xuất!', 'success')
    return redirect(url_for('admin.admin_login'))


# Trang dashboard dành cho admin
@admin_bp.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('admin.admin_login'))
    return render_template('admin/admin_dashboard.html')
