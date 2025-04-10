from flask import Blueprint, render_template, redirect, url_for, session, flash, request

from utils.db_supabase import (
    get_all_employees,
    get_total_employees,
    get_total_bookings,
    get_total_revenue,
    add_employee,
    update_employee
)

manager_bp = Blueprint('manager', __name__)

# Trang dashboard của quản lý
@manager_bp.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user or user.get('role') != 'manager':
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('admin.admin_login'))
    return render_template('manager/manager_dashboard.html')

# Xem thống kê báo cáo
@manager_bp.route('/reports')
def reports():
    user = session.get('user')
    if not user or user.get('role') != 'manager':
        flash('Bạn không có quyền truy cập!', 'error')
        return redirect(url_for('admin.admin_login'))

    total_employees = len(get_total_employees().data)
    total_bookings = len(get_total_bookings().data)
    total_revenue = get_total_revenue()

    return render_template('manager/reports.html',
                           total_employees=total_employees,
                           total_bookings=total_bookings,
                           total_revenue=total_revenue)

# Thêm nhân viên mới
@manager_bp.route('/employees/add', methods=['GET', 'POST'])
def add_employee_view():
    user = session.get('user')
    if not user or user.get('role') != 'manager':
        flash('Bạn không có quyền truy cập!', 'error')
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        data = {
            "hoten": request.form.get("hoten"),
            "email": request.form.get("email"),
            "sodienthoai": request.form.get("sodienthoai"),
            "matkhau": request.form.get("matkhau"),
            "chucvu": request.form.get("chucvu")
        }
        add_employee(data)
        flash("Đã thêm nhân viên mới thành công!", "success")
        return redirect(url_for('manager.manage_employees'))

    return render_template('manager/add_employee.html')

# Cập nhật thông tin nhân viên
@manager_bp.route('/employees/update/<string:manv>', methods=['GET', 'POST'])
def update_employee_view(manv):
    user = session.get('user')
    if not user or user.get('role') != 'manager':
        flash('Bạn không có quyền truy cập!', 'error')
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        data = {
            "hoten": request.form.get("hoten"),
            "email": request.form.get("email"),
            "sodienthoai": request.form.get("sodienthoai"),
            "matkhau": request.form.get("matkhau"),
            "chucvu": request.form.get("chucvu")
        }
        update_employee(manv, data)
        flash("Cập nhật thông tin thành công!", "success")
        return redirect(url_for('manager.manage_employees'))

    return render_template('manager/update_employee.html', manv=manv)

# Quản lý danh sách nhân viên (gộp cả employee_list)
@manager_bp.route('/employees')
def manage_employees():
    user = session.get('user')
    if not user or user.get('role') != 'manager':
        flash('Bạn không có quyền truy cập!', 'error')
        return redirect(url_for('admin.admin_login'))

    res = get_all_employees()
    return render_template('manager/manage_employees.html', employees=res.data)
