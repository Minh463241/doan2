from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_supabase import (
    get_all_employees, get_rooms, get_total_bookings,
    get_total_employees, get_total_revenue, supabase,
    insert_employee, update_employee, get_room_by_id, update_room
)
import logging
import re

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Decorator kiểm tra đăng nhập
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user' not in session or session['user'].get('role') != 'manager':
            flash('Bạn cần đăng nhập với vai trò quản lý để truy cập trang này.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@manager_bp.route("/dashboard")
@login_required
def dashboard():
    try:
        rooms = get_rooms() or []
        employees = get_all_employees() or []

        # ✅ Truy vấn hóa đơn + liên kết khách hàng & đặt phòng chỉ trong 1 request
        hoadon_res = supabase.table("hoadon").select(
            "mahoadon, madatphong, makhachhang, ngaylap, tongtien, phuongthucthanhtoan, "
            "khachhang(hoten), datphong(magiaodichpaypal)"
        ).execute()
        hoadon_list = hoadon_res.data or []

        # Làm phẳng dữ liệu trả về
        for hd in hoadon_list:
            hd["tenkhachhang"] = hd.get("khachhang", {}).get("hoten", "Không rõ")
            hd["magiaodichpaypal"] = hd.get("datphong", {}).get("magiaodichpaypal", "---")
            hd.pop("khachhang", None)
            hd.pop("datphong", None)

        # ✅ Lấy các thống kê tổng hợp
        total_employees = get_total_employees()
        total_bookings = get_total_bookings()
        total_revenue = get_total_revenue()

        logger.info(
            f"Thống kê - Nhân viên: {total_employees}, "
            f"Đặt phòng: {total_bookings}, "
            f"Doanh thu: {total_revenue}"
        )

    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu dashboard: {e}")
        hoadon_list = []
        total_employees = total_bookings = total_revenue = 0

    return render_template(
        "manager/manager_dashboard.html",
        total_employees=total_employees,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        rooms=rooms,
        employees=employees,
        hoadon_list=hoadon_list,
        user=session.get("user")
    )



# Tuyến đường xem báo cáo
@manager_bp.route("/reports")
@login_required
def reports():
    total_employees = get_total_employees()
    total_bookings = get_total_bookings()
    total_revenue = get_total_revenue()

    return render_template("manager/reports.html",
                           total_employees=total_employees,
                           total_bookings=total_bookings,
                           total_revenue=total_revenue)

# Thêm phòng
@manager_bp.route("/rooms/add", methods=['GET', 'POST'])
@login_required
def add_room():
    if request.method == 'POST':
        try:
            loaiphong = request.form['loaiphong'].strip()
            giaphong = float(request.form['giaphong'])
            succhua = int(request.form['succhua'])
            trangthai = request.form['trangthai']
            dientich = int(request.form['dientich'])

            # Validate dữ liệu
            if giaphong < 0:
                raise ValueError("Giá phòng không thể âm.")
            if succhua <= 0 or dientich <= 0:
                raise ValueError("Sức chứa và diện tích phải lớn hơn 0.")
            valid_statuses = ["trong", "dang_su_dung", "dang_bao_tri"]
            if trangthai not in valid_statuses:
                raise ValueError("Trạng thái không hợp lệ. Chọn: trong, dang_su_dung, dang_bao_tri.")

            hinhanh_file = request.files.get('hinhanh')
            hinhanh_url = None
            if hinhanh_file and hinhanh_file.filename:
                allowed_extensions = {'.jpg', '.jpeg', '.png'}
                if not any(hinhanh_file.filename.lower().endswith(ext) for ext in allowed_extensions):
                    raise ValueError("Định dạng ảnh không được hỗ trợ.")
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
            if response.data:
                flash('Thêm phòng thành công!', 'success')
            else:
                flash('Thêm phòng thất bại.', 'error')
        except ValueError as ve:
            flash(f'Dữ liệu không hợp lệ: {str(ve)}', 'error')
        except Exception as e:
            logger.error(f"Lỗi khi thêm phòng: {str(e)}")
            flash(f'Có lỗi: {str(e)}', 'error')

        return redirect(url_for('manager.dashboard') + '#rooms')

    return render_template('manager/add_room.html')

# Chỉnh sửa phòng
@manager_bp.route("/rooms/edit/<maphong>", methods=['GET', 'POST'])
@login_required
def edit_room(maphong):
    room = get_room_by_id(maphong)
    if not room:
        flash('Phòng không tồn tại.', 'error')
        return redirect(url_for('manager.dashboard') + '#rooms')

    if request.method == 'POST':
        try:
            loaiphong = request.form['loaiphong'].strip()
            giaphong = float(request.form['giaphong'])
            succhua = int(request.form['succhua'])
            trangthai = request.form['trangthai']
            dientich = int(request.form['dientich'])

            # Validate dữ liệu
            if giaphong < 0:
                raise ValueError("Giá phòng không thể âm.")
            if succhua <= 0 or dientich <= 0:
                raise ValueError("Sức chứa và diện tích phải lớn hơn 0.")
            valid_statuses = ["trong", "dang_su_dung", "dang_bao_tri"]
            if trangthai not in valid_statuses:
                raise ValueError("Trạng thái không hợp lệ. Chọn: trong, dang_su_dung, dang_bao_tri.")
            if not loaiphong:
                raise ValueError("Loại phòng không được để trống.")

            # Kiểm tra trạng thái phòng trước khi cập nhật
            if trangthai == 'trong':
                active_bookings = supabase.table('datphong')\
                    .select('madatphong')\
                    .eq('maphong', maphong)\
                    .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])\
                    .execute().data
                if active_bookings:
                    raise ValueError("Không thể đặt trạng thái 'trong' vì phòng đang có đặt phòng hoạt động.")

            hinhanh_file = request.files.get('hinhanh')
            hinhanh_url = None
            if hinhanh_file and hinhanh_file.filename:
                allowed_extensions = {'.jpg', '.jpeg', '.png'}
                if not any(hinhanh_file.filename.lower().endswith(ext) for ext in allowed_extensions):
                    raise ValueError("Định dạng ảnh không được hỗ trợ.")
                from utils.upload_cloudinary import upload_image_to_cloudinary
                hinhanh_url = upload_image_to_cloudinary(hinhanh_file)

            data_update = {
                'loaiphong': loaiphong,
                'giaphong': giaphong,
                'succhua': succhua,
                'trangthai': trangthai,
                'dientich': dientich
            }
            if hinhanh_url:
                data_update['hinhanh'] = hinhanh_url

            response = update_room(maphong, data_update)
            if response:
                flash('Cập nhật phòng thành công!', 'success')
            else:
                flash('Cập nhật phòng thất bại.', 'error')

        except ValueError as ve:
            flash(f'Dữ liệu không hợp lệ: {str(ve)}', 'error')
            return render_template('manager/edit_room.html', room=room, form_data=request.form)
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật phòng {maphong}: {str(e)}")
            flash(f'Lỗi hệ thống: {str(e)}', 'error')
            return render_template('manager/edit_room.html', room=room, form_data=request.form)

        return redirect(url_for('manager.dashboard') + '#rooms')

    return render_template('manager/edit_room.html', room=room)

# Xóa phòng
# Xóa phòng (Cách 1 - an toàn, kiểm tra liên kết trước)
@manager_bp.route("/rooms/delete/<maphong>", methods=['POST'])
@login_required
def delete_room(maphong):
    try:
        # 1️⃣ Kiểm tra xem phòng có đơn đặt phòng liên quan không
        active_bookings = supabase.table('datphong')\
            .select('madatphong, trangthai')\
            .eq('maphong', maphong)\
            .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã check-in', 'Đã thanh toán'])\
            .execute().data

        if active_bookings:
            flash('❌ Không thể xóa phòng này vì đang có hoặc từng có đơn đặt phòng liên quan.', 'error')
            logger.warning(f"Phòng {maphong} có đơn đặt phòng, không thể xóa.")
            return redirect(url_for('manager.dashboard') + '#rooms')

        # 2️⃣ Nếu không có booking → cho phép xóa
        response = supabase.table("phong").delete().eq("maphong", maphong).execute()
        if response.data:
            flash('✅ Xóa phòng thành công!', 'success')
            logger.info(f"Đã xóa phòng {maphong}")
        else:
            flash('❌ Xóa phòng thất bại.', 'error')
            logger.warning(f"Không thể xóa phòng {maphong}, không có dữ liệu trả về.")

    except Exception as e:
        logger.error(f"Lỗi khi xóa phòng {maphong}: {str(e)}")
        flash(f'Lỗi khi xóa phòng: {str(e)}', 'error')

    return redirect(url_for('manager.dashboard') + '#rooms')


# Thêm nhân viên
@manager_bp.route("/employees/add", methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        try:
            hoten = request.form['hoten'].strip()
            chucvu = request.form['chucvu'].strip()
            email = request.form['email'].strip()
            matkhau = request.form['matkhau']
            sodienthoai = request.form['sodienthoai'].strip()

            # Kiểm tra định dạng email
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_pattern, email):
                raise ValueError('Email không hợp lệ.')

            # Kiểm tra định dạng số điện thoại
            phone_pattern = r'^\d{10}$'
            if not re.match(phone_pattern, sodienthoai):
                raise ValueError('Số điện thoại không hợp lệ (phải có 10 chữ số).')

            # Kiểm tra email trùng lặp
            existing_email = supabase.table("nhanvien").select("*").eq("email", email).execute()
            if existing_email.data:
                raise ValueError('Email đã được sử dụng.')

            response = insert_employee({
                'hoten': hoten,
                'chucvu': chucvu,
                'email': email,
                'matkhau': matkhau,
                'sodienthoai': sodienthoai
            })

            if response:
                flash('Thêm nhân viên thành công!', 'success')
            else:
                flash('Thêm nhân viên thất bại.', 'error')
        except ValueError as ve:
            flash(f'Dữ liệu không hợp lệ: {str(ve)}', 'error')
        except Exception as e:
            logger.error(f"Lỗi khi thêm nhân viên: {str(e)}")
            flash(f'Có lỗi: {str(e)}', 'error')

        return redirect(url_for('manager.dashboard') + '#employees')


    return render_template('manager/add_employee.html')

# Chi tiết nhân viên
@manager_bp.route("/employees/detail/<manv>")
@login_required
def employee_detail(manv):
    try:
        response = supabase.table("nhanvien").select("*").eq("manhanvien", manv).execute()
        if not response.data:
            flash('Nhân viên không tồn tại.', 'error')
            return redirect(url_for('manager.dashboard') + '#employees')


        employee = response.data[0]
        return render_template('manager/employee_detail.html', employee=employee)
    except Exception as e:
        logger.error(f"Lỗi khi lấy chi tiết nhân viên {manv}: {str(e)}")
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('manager.dashboard') + '#employees')



# Chỉnh sửa nhân viên
@manager_bp.route("/employees/edit/<manv>", methods=['GET', 'POST'])
@login_required
def edit_employee(manv):
    try:
        # Lấy thông tin nhân viên
        employee_response = supabase.table("nhanvien").select("*").eq("manhanvien", manv).execute()
        if not employee_response.data:
            flash('Nhân viên không tồn tại.', 'error')
            return redirect(url_for('manager.dashboard'))

        employee = employee_response.data[0]

        if request.method == 'POST':
            try:
                hoten = request.form['hoten'].strip()
                chucvu = request.form['chucvu'].strip()
                email = request.form['email'].strip()
                sodienthoai = request.form['sodienthoai'].strip()
                matkhau = request.form['matkhau'] if request.form['matkhau'] else employee['matkhau']

                # Kiểm tra định dạng email
                email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
                if not re.match(email_pattern, email):
                    raise ValueError('Email không hợp lệ.')

                # Kiểm tra định dạng số điện thoại (10 chữ số)
                phone_pattern = r'^\d{10}$'
                if not re.match(phone_pattern, sodienthoai):
                    raise ValueError('Số điện thoại không hợp lệ (phải có 10 chữ số).')

                # Kiểm tra email trùng lặp với nhân viên khác
                existing_email = supabase.table("nhanvien").select("*").eq("email", email).neq("manhanvien", manv).execute()
                if existing_email.data:
                    raise ValueError('Email đã được sử dụng bởi nhân viên khác.')

                # Cập nhật nhân viên
                response = update_employee(manv, {
                    'hoten': hoten,
                    'chucvu': chucvu,
                    'email': email,
                    'matkhau': matkhau,
                    'sodienthoai': sodienthoai
                })

                if response:
                    flash('Cập nhật nhân viên thành công!', 'success')
                else:
                    flash('Cập nhật nhân viên thất bại.', 'error')

            except ValueError as ve:
                flash(f'Dữ liệu không hợp lệ: {str(ve)}', 'error')
                return render_template('manager/edit_employee.html', employee=employee, form_data=request.form)
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật nhân viên {manv}: {str(e)}")
                flash(f'Có lỗi: {str(e)}', 'error')
                return render_template('manager/edit_employee.html', employee=employee, form_data=request.form)

            # Sau khi cập nhật xong → quay về dashboard
            return redirect(url_for('manager.dashboard'))

        # Nếu là GET → render form chỉnh sửa
        return render_template('manager/edit_employee.html', employee=employee)

    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin nhân viên {manv}: {str(e)}")
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('manager.dashboard'))


@manager_bp.route("/employees/delete/<manv>", methods=['POST'])
@login_required
def delete_employee(manv):
    try:
        response = supabase.table("nhanvien").delete().eq("manhanvien", manv).execute()
        if response.data:
            flash('Xóa nhân viên thành công!', 'success')
            logger.info(f"Đã xóa nhân viên mã {manv}")
        else:
            flash('Không tìm thấy nhân viên để xóa!', 'error')
            logger.warning(f"Không tìm thấy nhân viên với mã {manv}")
    except Exception as e:
        logger.error(f"Lỗi khi xóa nhân viên {manv}: {str(e)}")
        flash(f'Lỗi khi xóa nhân viên: {str(e)}', 'error')

    return redirect(url_for('manager.dashboard'))
