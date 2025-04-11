from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_supabase import (
    get_all_employees, get_rooms, get_total_bookings,
    get_total_employees, get_total_revenue, supabase, insert_employee, update_employee
)

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")

# Kiểm tra đăng nhập và vai trò quản lý
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user' not in session or session['user'].get('role') != 'manager':
            flash('Bạn cần đăng nhập với vai trò quản lý để truy cập trang này.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Trang chính của quản lý
@manager_bp.route("/dashboard")
@login_required
def dashboard():
    # Lấy thống kê
    total_employees = len(get_total_employees().data)
    total_bookings = len(get_total_bookings().data)
    total_revenue = get_total_revenue()

    # Lấy danh sách phòng và nhân viên
    rooms = get_rooms().data
    employees = get_all_employees().data

    # Lấy danh sách hóa đơn đã thanh toán
    hoadon_res = supabase.table("hoadon").select("*").eq("trangthai", "đã thanh toán").execute()
    hoadon_list = hoadon_res.data

    # Gắn tên khách hàng vào hóa đơn
    for hd in hoadon_list:
        ma_kh = hd.get("makhachhang")
        if ma_kh:
            kh_res = supabase.table("khachhang").select("hoten").eq("makhachhang", ma_kh).single().execute()
            hd["tenkhachhang"] = kh_res.data["hoten"] if kh_res.data else "Không rõ"
        else:
            hd["tenkhachhang"] = "Không rõ"

    return render_template("manager/manager_dashboard.html",
                          total_employees=total_employees,
                          total_bookings=total_bookings,
                          total_revenue=total_revenue,
                          rooms=rooms,
                          employees=employees,
                          hoadon_list=hoadon_list,
                          user=session.get("user"))
    
@manager_bp.route("/rooms/add", methods=['GET', 'POST'])
@login_required
def add_room():
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        loaiphong = request.form['loaiphong']
        giaphong = float(request.form['giaphong'])
        succhua = int(request.form['succhua'])       # Lấy sức chứa
        trangthai = request.form['trangthai']
        dientich = int(request.form['dientich'])       # Lấy diện tích
        hinhanh = request.files.get('hinhanh')         # Nếu cần xử lý file hình ảnh

        # Xây dựng data insert cho Supabase
        data_insert = {
            'loaiphong': loaiphong,
            'giaphong': giaphong,
            'succhua': succhua,
            'trangthai': trangthai,
            'dientich': dientich,
            # Nếu xử lý file hình ảnh, có thể thêm trường 'hinhanh': file_path hoặc URL
        }

        response = supabase.table("phong").insert(data_insert).execute()

        if response.data:
            flash('Thêm phòng thành công!', 'success')
        else:
            flash('Có lỗi xảy ra khi thêm phòng.', 'error')
        return redirect(url_for('manager.dashboard') + '#rooms')

    return render_template('manager/add_room.html')


# Sửa phòng
@manager_bp.route("/rooms/edit/<maphong>", methods=['GET', 'POST'])
@login_required
def edit_room(maphong):
    # Lấy dữ liệu phòng từ Supabase để hiển thị form chỉnh sửa
    room_response = supabase.table("phong").select("*").eq("maphong", maphong).execute()
    if not room_response.data:
        flash('Phòng không tồn tại.', 'error')
        return redirect(url_for('manager.dashboard') + '#rooms')

    room = room_response.data[0]

    if request.method == 'POST':
        # Lấy dữ liệu chỉnh sửa từ form
        loaiphong = request.form['loaiphong']
        giaphong = float(request.form['giaphong'])
        succhua = int(request.form['succhua'])       # Lấy sức chứa mới
        trangthai = request.form['trangthai']
        dientich = int(request.form['dientich'])       # Lấy diện tích mới
        hinhanh = request.files.get('hinhanh')         # Nếu có cập nhật ảnh phòng

        # Xây dựng data cập nhật
        data_update = {
            'loaiphong': loaiphong,
            'giaphong': giaphong,
            'succhua': succhua,
            'trangthai': trangthai,
            'dientich': dientich,
            # Nếu xử lý file hình ảnh, thêm 'hinhanh': file_path hoặc URL
        }

        response = supabase.table("phong").update(data_update).eq("maphong", maphong).execute()

        if response.data:
            flash('Cập nhật phòng thành công!', 'success')
        else:
            flash('Có lỗi xảy ra khi cập nhật phòng.', 'error')
        return redirect(url_for('manager.dashboard') + '#rooms')

    return render_template('manager/edit_room.html', room=room)

# Xóa phòng
@manager_bp.route("/rooms/delete/<maphong>")
@login_required
def delete_room(maphong):
    response = supabase.table("phong").delete().eq("maphong", maphong).execute()
    if response.data:
        flash('Xóa phòng thành công!', 'success')
    else:
        flash('Có lỗi xảy ra khi xóa phòng.', 'error')
    return redirect(url_for('manager.dashboard') + '#rooms')

# Thêm nhân viên mới
@manager_bp.route("/employees/add", methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        hoten = request.form['hoten']
        chucvu = request.form['chucvu']
        email = request.form['email']
        matkhau = request.form['matkhau']

        # Kiểm tra trùng email thôi
        existing_email = supabase.table("nhanvien").select("*").eq("email", email).execute()
        if existing_email.data:
            flash('Email đã được sử dụng. Vui lòng chọn email khác.', 'error')
            return redirect(url_for('manager.add_employee'))

        response = insert_employee({
            'hoten': hoten,
            'chucvu': chucvu,
            'email': email,
            'matkhau': matkhau
        })

        if response.data:
            flash('Thêm nhân viên thành công!', 'success')
        else:
            flash('Có lỗi xảy ra khi thêm nhân viên.', 'error')
        return redirect(url_for('manager.dashboard') + '#employees')

    return render_template('manager/add_employee.html')

# Xem chi tiết nhân viên
@manager_bp.route("/employees/detail/<manv>")
@login_required
def employee_detail(manv):
    employee_response = supabase.table("nhanvien").select("*").eq("manv", manv).execute()
    if not employee_response.data:
        flash('Nhân viên không tồn tại.', 'error')
        return redirect(url_for('manager.dashboard') + '#employees')

    employee = employee_response.data[0]
    return render_template('manager/employee_detail.html', employee=employee)

# Sửa nhân viên
@manager_bp.route("/employees/edit/<manv>", methods=['GET', 'POST'])
@login_required
def edit_employee(manv):
    employee_response = supabase.table("nhanvien").select("*").eq("manv", manv).execute()
    if not employee_response.data:
        flash('Nhân viên không tồn tại.', 'error')
        return redirect(url_for('manager.dashboard') + '#employees')

    employee = employee_response.data[0]

    if request.method == 'POST':
        hoten = request.form['hoten']
        chucvu = request.form['chucvu']
        email = request.form['email']

        # Kiểm tra email mới có trùng với email khác không
        existing_email = supabase.table("nhanvien").select("*").eq("email", email).neq("manv", manv).execute()
        if existing_email.data:
            flash('Email đã được sử dụng bởi nhân viên khác.', 'error')
            return redirect(url_for('manager.edit_employee', manv=manv))

        # Cập nhật nhân viên
        response = update_employee(manv, {
            'hoten': hoten,
            'chucvu': chucvu,
            'email': email
        })

        if response.data:
            flash('Cập nhật nhân viên thành công!', 'success')
        else:
            flash('Có lỗi xảy ra khi cập nhật nhân viên.', 'error')
        return redirect(url_for('manager.dashboard') + '#employees')

    return render_template('manager/edit_employee.html', employee=employee)

# Xóa nhân viên
@manager_bp.route("/employees/delete/<manv>")
@login_required
def delete_employee(manv):
    response = supabase.table("nhanvien").delete().eq("manv", manv).execute()
    if response.data:
        flash('Xóa nhân viên thành công!', 'success')
    else:
        flash('Có lỗi xảy ra khi xóa nhân viên.', 'error')
    return redirect(url_for('manager.dashboard') + '#employees')