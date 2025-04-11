from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_supabase import (
    get_all_employees, get_rooms, get_total_bookings,
    get_total_employees, get_total_revenue, supabase,
    insert_employee, update_employee
)

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")

# Decorator kiểm tra đăng nhập
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user' not in session or session['user'].get('role') != 'manager':
            flash('Bạn cần đăng nhập với vai trò quản lý để truy cập trang này.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Trang dashboard quản lý
@manager_bp.route("/dashboard")
@login_required
def dashboard():
    total_employees = len(get_total_employees().data or [])
    total_bookings = len(get_total_bookings().data or [])
    total_revenue = get_total_revenue()

    rooms = get_rooms().data or []
    employees = get_all_employees().data or []

    hoadon_res = supabase.table("hoadon").select("*").eq("trangthai", "đã thanh toán").execute()
    hoadon_list = hoadon_res.data or []

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

# Thêm phòng
@manager_bp.route("/rooms/add", methods=['GET', 'POST'])
@login_required
def add_room():
    if request.method == 'POST':
        try:
            loaiphong = request.form['loaiphong']
            giaphong = float(request.form['giaphong'])
            succhua = int(request.form['succhua'])
            trangthai = request.form['trangthai']
            dientich = int(request.form['dientich'])

            hinhanh_file = request.files.get('hinhanh')
            hinhanh_url = None
            if hinhanh_file and hinhanh_file.filename:
                from utils.upload_cloudinary import upload_image_to_cloudinary
                hinhanh_url = upload_image_to_cloudinary(hinhanh_file)

            data_insert = {
                'loaiphong': loaiphong,
                'giaphong': giaphong,
                'succhua': succhua,
                'trangthai': trangthai,
                'dientich': dientich
            }
            if hinhanh_url:
                data_insert['hinhanh'] = hinhanh_url

            response = supabase.table("phong").insert(data_insert).execute()
            flash('Thêm phòng thành công!', 'success' if response.data else 'error')
        except Exception as e:
            flash(f'Có lỗi: {str(e)}', 'error')

        return redirect(url_for('manager.dashboard') + '#rooms')

    return render_template('manager/add_room.html')

# Chỉnh sửa phòng
@manager_bp.route("/rooms/edit/<maphong>", methods=['GET', 'POST'])
@login_required
def edit_room(maphong):
    room_response = supabase.table("phong").select("*").eq("maphong", maphong).execute()
    if not room_response.data:
        flash('Phòng không tồn tại.', 'error')
        return redirect(url_for('manager.dashboard') + '#rooms')

    room = room_response.data[0]

    if request.method == 'POST':
        try:
            loaiphong = request.form['loaiphong']
            giaphong = float(request.form['giaphong'])
            succhua = int(request.form['succhua'])
            trangthai = request.form['trangthai']
            dientich = int(request.form['dientich'])

            hinhanh_file = request.files.get('hinhanh')
            hinhanh_url = None
            if hinhanh_file and hinhanh_file.filename:
                from utils.upload_cloudinary import upload_image_to_cloudinary
                hinhanh_url = upload_image_to_cloudinary(hinhanh_file, folder='rooms')

            data_update = {
                'loaiphong': loaiphong,
                'giaphong': giaphong,
                'succhua': succhua,
                'trangthai': trangthai,
                'dientich': dientich
            }
            if hinhanh_url:
                data_update['hinhanh'] = hinhanh_url

            response = supabase.table("phong").update(data_update).eq("maphong", maphong).execute()
            flash('Cập nhật phòng thành công!' if response.data else 'Cập nhật thất bại.', 'success' if response.data else 'error')
        except Exception as e:
            flash(f'Có lỗi: {str(e)}', 'error')

        return redirect(url_for('manager.dashboard') + '#rooms')

    return render_template('manager/edit_room.html', room=room)

# Xoá phòng
@manager_bp.route("/rooms/delete/<maphong>")
@login_required
def delete_room(maphong):
    response = supabase.table("phong").delete().eq("maphong", maphong).execute()
    flash('Xóa phòng thành công!' if response.data else 'Xóa thất bại.', 'success' if response.data else 'error')
    return redirect(url_for('manager.dashboard') + '#rooms')

# Thêm nhân viên
@manager_bp.route("/employees/add", methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        hoten = request.form['hoten']
        chucvu = request.form['chucvu']
        email = request.form['email']
        matkhau = request.form['matkhau']

        existing_email = supabase.table("nhanvien").select("*").eq("email", email).execute()
        if existing_email.data:
            flash('Email đã được sử dụng.', 'error')
            return redirect(url_for('manager.add_employee'))

        response = insert_employee({
            'hoten': hoten,
            'chucvu': chucvu,
            'email': email,
            'matkhau': matkhau
        })

        flash('Thêm nhân viên thành công!' if response.data else 'Thêm thất bại.', 'success' if response.data else 'error')
        return redirect(url_for('manager.dashboard') + '#employees')

    return render_template('manager/add_employee.html')

# Chi tiết nhân viên
@manager_bp.route("/employees/detail/<manv>")
@login_required
def employee_detail(manv):
    response = supabase.table("nhanvien").select("*").eq("manv", manv).execute()
    if not response.data:
        flash('Nhân viên không tồn tại.', 'error')
