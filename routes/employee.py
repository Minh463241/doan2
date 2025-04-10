from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from supabase import create_client
from config import Config

employee_bp = Blueprint('employee', __name__, url_prefix="/employee")

# Route xem danh sách nhân viên (chỉ dành cho quản lý, admin)
@employee_bp.route('/list')
def list_employees():
    if session.get('user', {}).get('role') not in ['manager', 'admin']:
        return redirect(url_for('auth.login'))
    
    from utils.db_supabase import get_all_employees
    employees_res = get_all_employees()
    employees = employees_res.data if employees_res and employees_res.data else []
    return render_template("employee_list.html", employees=employees)


# Route chức năng confirm booking dành cho nhân viên
@employee_bp.route('/confirm-booking', methods=['GET', 'POST'])
def confirm_booking():
    user = session.get('user')
    if not user or user.get('role') != 'nhanvien':
        flash('Bạn không có quyền truy cập chức năng này!', 'error')
        return redirect(url_for('auth.login'))
    
    # Tạo kết nối Supabase thông qua config
    from supabase import create_client
    from config import Config
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        try:
            madatphong = int(request.form.get('madatphong'))
        except (TypeError, ValueError):
            flash('Mã đặt phòng không hợp lệ!', 'error')
            return redirect(url_for('employee.confirm_booking'))
            
        action = request.form.get('action')

        booking = supabase.table('datphong')\
            .select('maphong, trangthai')\
            .eq('madatphong', madatphong).execute()
        if not booking.data:
            flash('Đặt phòng không tồn tại!', 'error')
            return redirect(url_for('employee.confirm_booking'))

        maphong = booking.data[0]['maphong']

        if action == 'confirm':
            supabase.table('datphong')\
                .update({'trangthai': 'Đã xác nhận'})\
                .eq('madatphong', madatphong).execute()
            flash(f'Đã xác nhận đặt phòng #{madatphong}!', 'success')
        elif action == 'reject':
            supabase.table('datphong')\
                .update({'trangthai': 'Đã hủy'})\
                .eq('madatphong', madatphong).execute()
            # Chú ý: Sửa lại trạng thái phòng về 'Trống' thay vì 'available' nếu như trong DB bạn dùng 'Trống'
            supabase.table('phong')\
                .update({'trangthai': 'Trống'})\
                .eq('maphong', maphong).execute()
            flash(f'Đã từ chối đặt phòng #{madatphong}!', 'success')

        return redirect(url_for('employee.confirm_booking'))

    bookings = supabase.table('datphong')\
                .select('*')\
                .eq('trangthai', 'Chờ xác nhận')\
                .execute().data
    return render_template('employee/confirm_booking.html', bookings=bookings)
