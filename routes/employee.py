from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from supabase import create_client
from config import Config

employee_bp = Blueprint('employee', __name__, url_prefix="/employee")

# Hàm kiểm tra vai trò nhân viên
def check_employee_role():
    user = session.get('user')
    return user and user.get('role') == 'nhanvien'

# Tuyến đường cho giao diện Quản lý đặt phòng của nhân viên
@employee_bp.route('/booking')
def employee_booking():
    if not check_employee_role():
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('admin.admin_login'))

    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        bookings_to_confirm = supabase.table('datphong')\
            .select('*')\
            .eq('trangthai', 'Chờ xác nhận')\
            .execute().data or []
        checkins = supabase.table('datphong')\
            .select('*')\
            .eq('trangthai', 'Đã xác nhận')\
            .execute().data or []
        all_bookings = supabase.table('datphong').select('*').execute().data or []
    except Exception as e:
        flash(f"Lỗi khi lấy dữ liệu: {str(e)}", 'error')
        return render_template('employee/employee_booking.html', bookings_to_confirm=[], checkins=[], all_bookings=[])
    
    return render_template('employee/employee_booking.html', 
                          bookings_to_confirm=bookings_to_confirm,
                          checkins=checkins,
                          all_bookings=all_bookings)


# Tuyến đường cho giao diện Quản lý dịch vụ của nhân viên
@employee_bp.route('/services')
def employee_services():
    if not check_employee_role():
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('auth.login'))

    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        # Lấy danh sách dịch vụ từ bảng 'dichvu'
        services = supabase.table('dichvu').select('*').execute().data or []
        
        # Lấy chi tiết dịch vụ đã đặt từ bảng 'chitietdichvu'
        booked_services = supabase.table('chitietdichvu') \
            .select('machitiet, madatphong, madichvu, soluong, thanhtien, ngayDat') \
            .execute().data or []
    except Exception as e:
        flash(f"Lỗi khi lấy dữ liệu: {str(e)}", 'error')
        return render_template('employee/employee_services.html', services=[], booked_services=[])
    
    return render_template('employee/employee_services.html', 
                          services=services,
                          booked_services=booked_services)



# Tuyến đường cho giao diện Quản lý khách hàng của nhân viên
@employee_bp.route('/customers', methods=['GET', 'POST'])
def employee_customers():
    if not check_employee_role():
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('admin.admin_login'))

    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    customer = None
    if request.method == 'POST':
        cccd = request.form.get('cccd')
        if not cccd:
            flash('Vui lòng nhập CCCD!', 'error')
        else:
            try:
                customer = supabase.table('khachhang').select('*').eq('cccd', cccd).execute().data
                if not customer:
                    flash('Không tìm thấy khách hàng!', 'error')
                else:
                    customer = customer[0]
            except Exception as e:
                flash(f"Lỗi: {str(e)}", 'error')

    try:
        customers = supabase.table('khachhang').select('*').execute().data or []
    except Exception as e:
        flash(f"Lỗi khi lấy dữ liệu: {str(e)}", 'error')
        customers = []
    
    return render_template('employee/employee_customers.html', customers=customers, customer=customer)

# Route tìm kiếm phòng theo ngày (dành cho nhân viên)
@employee_bp.route('/search-room', methods=['GET', 'POST'])
def search_room():
    if not check_employee_role():
        return jsonify({"success": False, "message": "Bạn không có quyền truy cập chức năng này!"}), 403
    
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    if request.method == 'POST':
        checkin_date = request.form.get('checkin_date')
        checkout_date = request.form.get('checkout_date')
        if not checkin_date or not checkout_date:
            return jsonify({"success": False, "message": "Vui lòng nhập ngày nhận và trả phòng!"}), 400
        try:
            available_rooms = supabase.table('phong').select('*').eq('trangthai', 'Trống').execute().data or []
            booked_rooms = supabase.table('datphong')\
                .select('maphong')\
                .eq('trangthai', 'Đã xác nhận')\
                .gte('ngaynhanphong', checkin_date)\
                .lte('ngaytraphong', checkout_date)\
                .execute().data or []
            booked_room_ids = {booking['maphong'] for booking in booked_rooms}
            available_rooms = [room for room in available_rooms if room['maphong'] not in booked_room_ids]
            return render_template('employee/employee_search_results.html', rooms=available_rooms)
        except Exception as e:
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500
    return render_template('employee/employee_search_room.html')

# Route chức năng confirm booking dành cho nhân viên
@employee_bp.route('/confirm-booking', methods=['GET', 'POST'])
def confirm_booking():
    if not check_employee_role():
        return jsonify({"success": False, "message": "Bạn không có quyền truy cập chức năng này!"}), 403
    
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            madatphong = int(data.get('madatphong'))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã đặt phòng không hợp lệ!"}), 400
            
        action = data.get('action')

        booking = supabase.table('datphong')\
            .select('maphong, trangthai')\
            .eq('madatphong', madatphong).execute()
        if not booking.data:
            return jsonify({"success": False, "message": "Đặt phòng không tồn tại!"}), 404

        maphong = booking.data[0]['maphong']

        try:
            if action == 'confirm':
                supabase.table('datphong')\
                    .update({'trangthai': 'Đã xác nhận'})\
                    .eq('madatphong', madatphong).execute()
                return jsonify({"success": True, "message": f"Đã xác nhận đặt phòng #{madatphong}!"})
            elif action == 'reject':
                supabase.table('datphong')\
                    .update({'trangthai': 'Đã hủy'})\
                    .eq('madatphong', madatphong).execute()
                supabase.table('phong')\
                    .update({'trangthai': 'Trống'})\
                    .eq('maphong', maphong).execute()
                return jsonify({"success": True, "message": f"Đã từ chối đặt phòng #{madatphong}!"})
            else:
                return jsonify({"success": False, "message": "Hành động không hợp lệ!"}), 400
        except Exception as e:
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        bookings = supabase.table('datphong')\
                    .select('*')\
                    .eq('trangthai', 'Chờ xác nhận')\
                    .execute().data or []
        return jsonify({"success": True, "bookings": bookings})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi khi lấy dữ liệu: {str(e)}"}), 500

# Route chức năng xác nhận check-in phòng
@employee_bp.route('/checkin', methods=['GET', 'POST'])
def checkin():
    if not check_employee_role():
        return jsonify({"success": False, "message": "Bạn không có quyền truy cập chức năng này!"}), 403
    
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            madatphong = int(data.get('madatphong'))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã đặt phòng không hợp lệ!"}), 400
            
        action = data.get('action')

        checkin_record = supabase.table('datphong')\
            .select('maphong, trangthai')\
            .eq('madatphong', madatphong).execute()
        if not checkin_record.data:
            return jsonify({"success": False, "message": "Đặt phòng không tồn tại!"}), 404

        maphong = checkin_record.data[0]['maphong']

        try:
            if action == 'checkin':
                supabase.table('datphong')\
                    .update({'trangthai': 'Đã check-in'})\
                    .eq('madatphong', madatphong).execute()
                supabase.table('phong')\
                    .update({'trangthai': 'Đã sử dụng'})\
                    .eq('maphong', maphong).execute()
                return jsonify({"success": True, "message": f"Đã xác nhận check-in cho đặt phòng #{madatphong}!"})
            else:
                return jsonify({"success": False, "message": "Hành động không hợp lệ!"}), 400
        except Exception as e:
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        checkins = supabase.table('datphong')\
                    .select('*')\
                    .eq('trangthai', 'Đã xác nhận')\
                    .execute().data or []
        return render_template('employee/employee_checkin.html', checkins=checkins)
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi khi lấy dữ liệu: {str(e)}"}), 500

# Trang dashboard dành cho nhân viên sau khi đăng nhập
@employee_bp.route('/dashboard')
def employee_dash_board():
    if not check_employee_role():
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('admin.admin_login'))

    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        bookings = supabase.table('datphong')\
                    .select('*')\
                    .eq('trangthai', 'Chờ xác nhận')\
                    .execute().data or []
    except Exception as e:
        flash(f"Lỗi khi lấy danh sách đặt phòng: {str(e)}", 'error')
        bookings = []
    return render_template('employee/employee_dashboard.html', user=session.get('user'), bookings=bookings)