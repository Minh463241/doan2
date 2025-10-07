from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from supabase import create_client
from config import Config
from utils.db_supabase import get_admin_by_email
import functools

supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

admin_bp = Blueprint('admin', __name__)

# Hàm decorator kiểm tra vai trò
def require_role(*allowed_roles):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            user = session.get('user')
            if not user:
                flash('Vui lòng đăng nhập để truy cập trang này!', 'error')
                return redirect(url_for('admin.admin_login'))
            role = user.get('role')
            if role not in allowed_roles:
                flash(f'Bạn không có quyền truy cập trang này! Vai trò yêu cầu: {", ".join(allowed_roles)}', 'error')
                session.pop('user', None)
                return redirect(url_for('admin.admin_login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        admin = get_admin_by_email(email)

        if admin:
            if admin.get("matkhau") == password:
                role = admin.get("chucvu", "").lower()
                valid_roles = ['admin', 'manager', 'letan', 'ketoan', 'donphong']
                if role not in valid_roles:
                    flash('Vai trò không hợp lệ!', 'error')
                    return redirect(url_for('admin.admin_login'))
                
                session['user'] = {'email': admin['email'], 'role': role, 'hoten': admin['hoten']}
                flash('Đăng nhập thành công!', 'success')
                
                if role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif role == 'manager':
                    return redirect(url_for('manager.dashboard'))
                elif role == 'letan':
                    return redirect(url_for('employee.letan_dashboard'))
                elif role == 'ketoan':
                    return redirect(url_for('employee.ketoan_dashboard'))
                elif role == 'donphong':
                    return redirect(url_for('employee.donphong_dashboard'))
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

@admin_bp.route('/dashboard')
@require_role('admin')
def dashboard():
    user = session.get('user')
    return render_template('admin/admin_dashboard.html', user=user)