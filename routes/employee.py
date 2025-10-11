from io import BytesIO
from flask import Blueprint, render_template, request, send_file, session, redirect, url_for, flash, jsonify
from supabase import create_client
from config import Config
import functools
from datetime import datetime, timedelta
import logging
from xhtml2pdf import pisa
from io import BytesIO

import json
from utils.db_supabase import (
    create_invoice, insert_booking, update_invoice_with_service, confirm_payment, get_unpaid_bookings_and_services,
    get_invoice_by_booking_id, get_service_by_id, get_all_services, get_available_rooms
)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

employee_bp = Blueprint('employee', __name__, url_prefix="/employee")

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

# Route cho dashboard của lễ tân
@employee_bp.route('/letan')
@require_role('letan')
def letan_dashboard():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        bookings = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .eq('trangthai', 'Chờ xác nhận')\
            .execute().data or []
        logger.info(f"Lấy danh sách đặt phòng: {len(bookings)} booking(s)")
        return render_template('employee/employee_letan_dashboard.html', user=user, bookings=bookings)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách đặt phòng: {str(e)}")
        flash('Lỗi khi lấy danh sách đặt phòng!', 'error')
        return render_template('employee/employee_letan_dashboard.html', user=user, bookings=[])

# Route cho dashboard của kế toán
@employee_bp.route('/ketoan')
@require_role('ketoan')
def ketoan_dashboard():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        today = datetime.now()
        start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
        end_of_month = (today.replace(day=1) + timedelta(days=31)).replace(day=1).strftime('%Y-%m-%d')
        revenue_data = supabase.table('hoadon')\
            .select('tongtien, tongtien_dichvu')\
            .gt('tongtien', 0)\
            .gte('ngaylap', start_of_month)\
            .lte('ngaylap', end_of_month)\
            .execute().data or []
        total_revenue = sum((item['tongtien'] or 0) + (item['tongtien_dichvu'] or 0) for item in revenue_data)
        services = get_all_services()
        logger.info(f"Doanh thu tháng: {total_revenue}, Số dịch vụ: {len(services)}")
        return render_template('employee/employee_ketoan_dashboard.html', 
                             user=user, 
                             services=services, 
                             total_revenue=total_revenue)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu kế toán: {str(e)}")
        flash('Lỗi khi lấy dữ liệu!', 'error')
        return render_template('employee/employee_ketoan_dashboard.html', 
                             user=user, 
                             services=[], 
                             total_revenue=0)

# Route cho quản lý hóa đơn (kế toán)
@employee_bp.route('/invoices')
@require_role('ketoan')
def employee_invoices():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        invoices = supabase.table('hoadon')\
            .select('mahoadon, madatphong, makhachhang, tongtien, phuongthucthanhtoan, ngaylap, tongtien_dichvu, datphong(maphong, ngaynhanphong, ngaytraphong), khachhang(hoten)')\
            .gt('tongtien', 0)\
            .execute().data or []
        logger.info(f"Lấy danh sách hóa đơn: {len(invoices)} hóa đơn")
        return render_template('employee/employee_invoices.html', user=user, invoices=invoices)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách hóa đơn: {str(e)}")
        flash('Lỗi khi lấy danh sách hóa đơn!', 'error')
        return render_template('employee/employee_invoices.html', user=user, invoices=[])

# Route cho theo dõi doanh thu (kế toán)
@employee_bp.route('/revenue', methods=['GET', 'POST'])
@require_role('ketoan')
def employee_revenue():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    start_date = request.form.get('start_date') if request.method == 'POST' else None
    end_date = request.form.get('end_date') if request.method == 'POST' else None

    try:
        query = supabase.table('hoadon')\
            .select('mahoadon, madatphong, ngaylap, tongtien, tongtien_dichvu, datphong(maphong), khachhang(hoten)')\
            .gt('tongtien', 0)

        if start_date and end_date:
            query = query.gte('ngaylap', start_date).lte('ngaylap', end_date)

        revenue_data = query.execute().data or []
        total_revenue = sum((item['tongtien'] or 0) + (item['tongtien_dichvu'] or 0) for item in revenue_data)
        logger.info(f"Doanh thu từ {start_date} đến {end_date}: {total_revenue}")
        return render_template('employee/employee_revenue.html', 
                             user=user,
                             revenue_data=revenue_data, 
                             total_revenue=total_revenue, 
                             start_date=start_date, 
                             end_date=end_date)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu doanh thu: {str(e)}")
        flash('Lỗi khi lấy dữ liệu doanh thu!', 'error')
        return render_template('employee/employee_revenue.html', 
                             user=user,
                             revenue_data=[], 
                             total_revenue=0)

# Route cho xác nhận thanh toán (kế toán)
@employee_bp.route('/payments', methods=['GET', 'POST'])
@require_role('ketoan')
def employee_payments():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            mahoadon = str(data.get('mahoadon'))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã hóa đơn không hợp lệ!"}), 400

        try:
            confirm_payment(mahoadon)
            # Cập nhật trạng thái thanh toán của dịch vụ liên quan
            invoice = supabase.table('hoadon').select('madatphong').eq('mahoadon', mahoadon).single().execute().data
            if invoice and invoice['madatphong']:
                supabase.table('chitietdichvu')\
                    .update({'trangthaithanhtoan': 'Đã thanh toán'})\
                    .eq('madatphong', invoice['madatphong'])\
                    .eq('trangthaithanhtoan', 'Chưa thanh toán')\
                    .execute()
            logger.info(f"Xác nhận thanh toán hóa đơn #{mahoadon}")
            return jsonify({"success": True, "message": f"Đã xác nhận thanh toán cho hóa đơn #{mahoadon}!"})
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận thanh toán: {str(e)}")
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        unpaid_data = get_unpaid_bookings_and_services()
        unpaid_bookings = unpaid_data["unpaid_bookings"]
        unpaid_services = unpaid_data["unpaid_services"]
        logger.info(f"Danh sách chưa thanh toán: {len(unpaid_bookings)} đặt phòng, {len(unpaid_services)} dịch vụ")
        return render_template('employee/employee_payments.html', 
                             user=user, 
                             unpaid_bookings=unpaid_bookings, 
                             unpaid_services=unpaid_services)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách chưa thanh toán: {str(e)}")
        flash('Lỗi khi lấy danh sách chưa thanh toán!', 'error')
        return render_template('employee/employee_payments.html', 
                             user=user, 
                             unpaid_bookings=[], 
                             unpaid_services=[])

# Route cho báo cáo tài chính (kế toán)
@employee_bp.route('/financial-report', methods=['GET', 'POST'])
@require_role('ketoan')
def employee_financial_report():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    year = int(request.form.get('year')) if request.method == 'POST' and request.form.get('year').isdigit() else datetime.now().year
    years = list(range(2020, datetime.now().year + 1))

    try:
        response = supabase.table('hoadon')\
            .select('mahoadon, madatphong, ngaylap, tongtien, tongtien_dichvu')\
            .gt('tongtien', 0)\
            .execute()

        revenue_data = response.data or []
        monthly_revenue = {month: 0 for month in range(1, 13)}
        for item in revenue_data:
            ngaylap = datetime.strptime(item['ngaylap'], '%Y-%m-%d')
            if ngaylap.year == year:
                month = ngaylap.month
                monthly_revenue[month] += (item['tongtien'] or 0) + (item['tongtien_dichvu'] or 0)

        total_revenue = sum(monthly_revenue.values())
        logger.info(f"Báo cáo tài chính năm {year}: {total_revenue}")
        return render_template('employee/employee_financial_report.html',
                              user=user,
                              monthly_revenue=monthly_revenue,
                              total_revenue=total_revenue,
                              year=year,
                              years=years)
    except Exception as e:
        logger.error(f"Lỗi khi tạo báo cáo tài chính: {str(e)}")
        flash('Lỗi khi tạo báo cáo tài chính!', 'error')
        return render_template('employee/employee_financial_report.html',
                              user=user,
                              monthly_revenue={month: 0 for month in range(1, 13)},
                              total_revenue=0,
                              year=year,
                              years=years)

# Route cho quản lý đặt phòng (lễ tân)
@employee_bp.route('/booking')
@require_role('letan')
def employee_booking():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        bookings_to_confirm = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .eq('trangthai', 'Chờ xác nhận')\
            .execute().data or []
        checkins = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .eq('trangthai', 'Đã xác nhận')\
            .execute().data or []
        all_bookings = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .execute().data or []
        logger.info(f"Quản lý đặt phòng: {len(bookings_to_confirm)} chờ xác nhận, {len(checkins)} đã xác nhận")
        return render_template('employee/employee_booking.html', 
                             user=user,
                             bookings_to_confirm=bookings_to_confirm,
                             checkins=checkins,
                             all_bookings=all_bookings)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu đặt phòng: {str(e)}")
        flash('Lỗi khi lấy dữ liệu!', 'error')
        return render_template('employee/employee_booking.html', user=user, bookings_to_confirm=[], checkins=[], all_bookings=[])

# Route cho xác nhận đặt phòng (lễ tân)
@employee_bp.route('/confirm-booking', methods=['GET', 'POST'])
@require_role('letan')
def confirm_booking():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'madatphong' not in data or 'action' not in data:
            return jsonify({"success": False, "message": "Dữ liệu gửi lên không hợp lệ!"}), 400

        try:
            madatphong = str(data.get('madatphong'))
            action = data.get('action')
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã đặt phòng hoặc hành động không hợp lệ!"}), 400

        if action not in ['confirm', 'reject']:
            return jsonify({"success": False, "message": "Hành động không hợp lệ!"}), 400

        try:
            booking = supabase.table('datphong')\
                .select('maphong, trangthai, ngaynhanphong, ngaytraphong')\
                .eq('madatphong', madatphong).single().execute().data
            if not booking:
                return jsonify({"success": False, "message": "Đặt phòng không tồn tại!"}), 404

            current_status = booking['trangthai']
            maphong = booking['maphong']
            ngaynhanphong = booking['ngaynhanphong']
            ngaytraphong = booking['ngaytraphong']

            if current_status != 'Chờ xác nhận':
                return jsonify({"success": False, "message": f"Đặt phòng #{madatphong} không thể xử lý vì trạng thái hiện tại là '{current_status}'!"}), 400

            # Kiểm tra xung đột đặt phòng
            conflicting_bookings = supabase.table('datphong')\
                .select('madatphong')\
                .eq('maphong', maphong)\
                .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])\
                .lte('ngaynhanphong', ngaytraphong)\
                .gte('ngaytraphong', ngaynhanphong)\
                .neq('madatphong', madatphong)\
                .execute().data
            if conflicting_bookings and action == 'confirm':
                return jsonify({"success": False, "message": "Phòng đã được đặt trong khoảng thời gian này!"}), 400

            if action == 'confirm':
                response = supabase.table('datphong')\
                    .update({'trangthai': 'Đã xác nhận'})\
                    .eq('madatphong', madatphong).execute()
                response_room = supabase.table('phong')\
                    .update({'trangthai': 'dang_su_dung'})\
                    .eq('maphong', maphong).execute()
                if not response.data or not response_room.data:
                    return jsonify({"success": False, "message": "Không thể cập nhật trạng thái đặt phòng!"}), 500
                logger.info(f"Xác nhận đặt phòng #{madatphong}")
                return jsonify({"success": True, "message": f"Đã xác nhận đặt phòng #{madatphong}!"})
            elif action == 'reject':
                response1 = supabase.table('datphong')\
                    .update({'trangthai': 'Đã hủy'})\
                    .eq('madatphong', madatphong).execute()
                response2 = supabase.table('phong')\
                    .update({'trangthai': 'trong'})\
                    .eq('maphong', maphong).execute()
                if not response1.data or not response2.data:
                    return jsonify({"success": False, "message": "Không thể cập nhật trạng thái khi từ chối!"}), 500
                logger.info(f"Từ chối đặt phòng #{madatphong}")
                return jsonify({"success": True, "message": f"Đã từ chối đặt phòng #{madatphong}!"})
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận đặt phòng #{madatphong}: {str(e)}")
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        bookings = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .eq('trangthai', 'Chờ xác nhận')\
            .execute().data or []
        logger.info(f"Lấy danh sách đặt phòng chờ xác nhận: {len(bookings)}")
        return jsonify({"success": True, "message": "Lấy danh sách đặt phòng thành công", "bookings": bookings})
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách đặt phòng: {str(e)}")
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500
    

@employee_bp.route('/paid-bookings', methods=['GET'])
@require_role('letan')
def paid_bookings():
    user = session.get('user') or {}
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        # Lấy TẤT CẢ hóa đơn (coi như đã thanh toán). Nếu bạn có cột trạng thái thanh toán thì thêm .eq(...)
        resp = supabase.table('hoadon').select('''
            mahoadon,
            tongtien,
            tongtien_dichvu,
            ngaylap,
            datphong(
                madatphong,
                phong(maphong, loaiphong),
                khachhang(hoten)
            )
        ''').order('mahoadon', desc=True).execute()

        data = resp.data or []

        paid_list = []
        for row in data:
            dp = row.get('datphong') or {}
            phong = dp.get('phong') or {}
            kh = dp.get('khachhang') or {}

            paid_list.append({
                'madatphong': dp.get('madatphong'),
                'mahoadon': row.get('mahoadon'),
                'maphong': phong.get('maphong'),
                'loaiphong': phong.get('loaiphong'),
                'hoten': kh.get('hoten'),
                'tongtien_tonghop': float(row.get('tongtien') or 0) + float(row.get('tongtien_dichvu') or 0),
            })

        # Lọc những hóa đơn mà vì lý do gì đó không có datphong (FK hỏng) để tránh None
        paid_list = [r for r in paid_list if r['madatphong'] is not None]

        # Debug nhẹ (xem log server)
        logger.info(f"paid_bookings count={len(paid_list)}; sample={paid_list[0] if paid_list else '[]'}")

        return render_template('employee/employee_paid_bookings.html',
                               user=user, paid_bookings=paid_list)

    except Exception as e:
        logger.exception(f"Lỗi lấy danh sách đã thanh toán: {e}")
        flash('Lỗi khi lấy danh sách!', 'error')
        return render_template('employee/employee_paid_bookings.html',
                               user=user, paid_bookings=[])


@employee_bp.route('/print-invoice-pdf/<int:madatphong>', methods=['GET'], endpoint='print_invoice_pdf')
@require_role('letan', 'ketoan')
def print_invoice_pdf(madatphong):
    """In hóa đơn PDF bằng xhtml2pdf (tương thích với Vercel)."""
    user = session.get('user') or {}
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

    try:
        # 1️⃣ Lấy thông tin hóa đơn
        invoice = get_invoice_by_booking_id(str(madatphong))
        if not invoice:
            flash('Không tìm thấy hóa đơn cho đặt phòng này!', 'error')
            return redirect(url_for('employee.paid_bookings'))

        # 2️⃣ Lấy thông tin đặt phòng
        booking = supabase.table('datphong') \
            .select('maphong, ngaynhanphong, ngaytraphong, tongtien') \
            .eq('madatphong', madatphong).single().execute().data
        if not booking:
            flash('Không tìm thấy đặt phòng!', 'error')
            return redirect(url_for('employee.paid_bookings'))

        # 3️⃣ Lấy chi tiết dịch vụ
        services = supabase.table('chitietdichvu') \
            .select('soluong, thanhtien, dichvu(tendichvu, giadichvu)') \
            .eq('madatphong', madatphong).execute().data or []

        nhan_vien_letan = user.get('ten') or user.get('username') or 'Không xác định'
        printed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Tính tiền
        tien_phong = float(invoice.get('tongtien') or booking.get('tongtien') or 0)
        tien_dich_vu_tu_ct = 0.0
        charges = []

        for sv in services:
            dv = sv.get('dichvu') or {}
            name = dv.get('tendichvu') or 'Dịch vụ'
            qty = sv.get('soluong') or 1
            unit_price = float(dv.get('giadichvu') or 0)
            amount = float(sv.get('thanhtien') or (unit_price * qty))
            tien_dich_vu_tu_ct += amount
            charges.append({
                'name': name,
                'qty': qty,
                'unit_price': unit_price,
                'amount': amount,
            })

        tien_dich_vu = float(invoice.get('tongtien_dichvu') or tien_dich_vu_tu_ct)
        so_tien = tien_phong + tien_dich_vu

        # 4️⃣ Render template
        html_str = render_template(
            'employee/print_invoice.html',
            mahoadon=invoice['mahoadon'],
            madatphong=madatphong,
            nguoi_lap=nhan_vien_letan,
            ngay_lap=invoice.get('ngaylap', printed_at),
            ngay_thanh_toan=printed_at,
            phong=booking['maphong'],
            tien_phong=tien_phong,
            tien_dich_vu=tien_dich_vu,
            so_tien=so_tien,
            charges=charges,
            nhan_vien_letan=nhan_vien_letan,
            printed_at=printed_at,
            user=user
        )

        # 5️⃣ Chuyển HTML → PDF bằng xhtml2pdf
        pdf_io = BytesIO()
        pisa_status = pisa.CreatePDF(html_str, dest=pdf_io)
        pdf_io.seek(0)

        if pisa_status.err:
            flash('Lỗi khi tạo file PDF!', 'error')
            return redirect(url_for('employee.paid_bookings'))

        filename = f"hoadon_{invoice['mahoadon']}.pdf"
        return send_file(pdf_io, mimetype='application/pdf',
                         as_attachment=True,
                         download_name=filename)

    except Exception as e:
        logger.exception(f"Lỗi khi tạo PDF cho đặt phòng #{madatphong}: {e}")
        flash('Lỗi khi tạo hóa đơn PDF!', 'error')
        return redirect(url_for('employee.paid_bookings'))


# Route cho xác nhận thanh toán đặt phòng (lễ tân)
@employee_bp.route('/confirm-payment', methods=['POST'])
@require_role('letan')
def confirm_payment_booking():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            madatphong = str(data.get('madatphong'))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã đặt phòng không hợp lệ!"}), 400

        try:
            booking = supabase.table('datphong')\
                .select('makhachhang, tongtien, trangthai, maphong')\
                .eq('madatphong', madatphong)\
                .single().execute().data
            if not booking:
                return jsonify({"success": False, "message": "Đặt phòng không tồn tại!"}), 404

            if booking['trangthai'] not in ['Đã xác nhận', 'Đã check-in']:
                return jsonify({"success": False, "message": f"Đặt phòng #{madatphong} không thể thanh toán vì trạng thái hiện tại là '{booking['trangthai']}'!"}), 400

            services = supabase.table('chitietdichvu')\
                .select('thanhtien')\
                .eq('madatphong', madatphong)\
                .eq('trangthaithanhtoan', 'Chưa thanh toán')\
                .execute().data or []
            total_service_cost = sum(item['thanhtien'] for item in services if item['thanhtien'])

            total_amount = booking['tongtien'] + total_service_cost
            invoice = create_invoice(madatphong, booking['makhachhang'], total_amount, 'PayPal')
            if not invoice:
                return jsonify({"success": False, "message": "Không thể tạo hóa đơn!"}), 500

            if total_service_cost > 0:
                supabase.table('hoadon')\
                    .update({'tongtien_dichvu': total_service_cost})\
                    .eq('mahoadon', invoice['mahoadon']).execute()
                supabase.table('chitietdichvu')\
                    .update({'trangthaithanhtoan': 'Đã thanh toán'})\
                    .eq('madatphong', madatphong)\
                    .eq('trangthaithanhtoan', 'Chưa thanh toán')\
                    .execute()

            response = supabase.table('datphong')\
                .update({'trangthai': 'Đã thanh toán'})\
                .eq('madatphong', madatphong).execute()
            if not response.data:
                return jsonify({"success": False, "message": "Không thể cập nhật trạng thái đặt phòng!"}), 500

            logger.info(f"Xác nhận thanh toán đặt phòng #{madatphong}, Hóa đơn #{invoice['mahoadon']}")
            return jsonify({"success": True, "message": f"Đã xác nhận thanh toán và tạo hóa đơn cho đặt phòng #{madatphong}!"})
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận thanh toán #{madatphong}: {str(e)}")
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

# Route cho quản lý dịch vụ (lễ tân)
@employee_bp.route('/services')
@require_role('letan')
def employee_services():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    try:
        services = get_all_services()
        booked_services = supabase.table('chitietdichvu') \
            .select('machitiet, madatphong, madichvu, soluong, thanhtien, trangthaithanhtoan, ngaydat, dichvu(tendichvu, giadichvu), datphong(maphong, khachhang(hoten))') \
            .execute().data or []
        logger.info(f"Quản lý dịch vụ: {len(services)} dịch vụ, {len(booked_services)} chi tiết dịch vụ")
        return render_template('employee/employee_services.html', 
                             user=user,
                             services=services,
                             booked_services=booked_services)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu dịch vụ: {str(e)}")
        flash('Lỗi khi lấy dữ liệu!', 'error')
        return render_template('employee/employee_services.html', user=user, services=[], booked_services=[])

# Route cho thêm dịch vụ (lễ tân, kế toán)
@employee_bp.route('/add-service', methods=['POST'])
@require_role('letan', 'ketoan')
def add_service():
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    data = request.get_json()
    try:
        madatphong = str(data.get('madatphong'))
        madichvu = str(data.get('madichvu'))
        soluong = int(data.get('soluong', 1))
        if soluong <= 0:
            raise ValueError("Số lượng phải lớn hơn 0.")
    except (TypeError, ValueError) as e:
        logger.error(f"Lỗi dữ liệu khi thêm dịch vụ: {str(e)}")
        return jsonify({"success": False, "message": str(e) if str(e) else "Dữ liệu không hợp lệ!"}), 400

    try:
        booking = supabase.table('datphong')\
            .select('trangthai')\
            .eq('madatphong', madatphong)\
            .single().execute().data
        if not booking or booking['trangthai'] not in ['Đã xác nhận', 'Đã thanh toán', 'Đã check-in']:
            return jsonify({"success": False, "message": "Đặt phòng không hợp lệ để thêm dịch vụ!"}), 400

        service = get_service_by_id(madichvu)
        if not service:
            return jsonify({"success": False, "message": "Dịch vụ không tồn tại!"}), 404

        thanhtien = service['giadichvu'] * soluong
        service_detail = {
            'madatphong': madatphong,
            'madichvu': madichvu,
            'soluong': soluong,
            'thanhtien': float(thanhtien),
            'ngaydat': datetime.now().isoformat(),  # Định dạng ISO cho TIMESTAMP WITH TIME ZONE
            'trangthaithanhtoan': 'Chưa thanh toán',
            'trangthai': 'Chưa xử lý'  # Giả định trạng thái ban đầu
        }
        response = supabase.table('chitietdichvu').insert(service_detail).execute()
        if not response.data:
            return jsonify({"success": False, "message": "Không thể thêm dịch vụ!"}), 500

        # Cập nhật hóa đơn nếu đã tồn tại
        invoice = get_invoice_by_booking_id(madatphong)
        if invoice:
            update_invoice_with_service(madatphong, thanhtien)
            logger.info(f"Thêm dịch vụ #{madichvu} cho đặt phòng #{madatphong}, cập nhật hóa đơn #{invoice['mahoadon']}")
        else:
            logger.info(f"Thêm dịch vụ #{madichvu} cho đặt phòng #{madatphong}, chưa có hóa đơn")

        return jsonify({"success": True, "message": "Đã thêm dịch vụ thành công!"})
    except Exception as e:
        logger.error(f"Lỗi khi thêm dịch vụ #{madichvu} cho đặt phòng #{madatphong}: {str(e)}")
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

# Route cho quản lý khách hàng (lễ tân và kế toán)
@employee_bp.route('/customers', methods=['GET', 'POST'])
@require_role('letan', 'ketoan')
def employee_customers():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    customer = None
    if request.method == 'POST':
        cccd = request.form.get('cccd')
        if not cccd:
            flash('Vui lòng nhập CCCD!', 'error')
        else:
            try:
                customer = supabase.table('khachhang')\
                    .select('*, hoadon(*, datphong(maphong, ngaynhanphong, ngaytraphong))')\
                    .eq('cccd', cccd).execute().data
                if not customer:
                    flash('Không tìm thấy khách hàng!', 'error')
                else:
                    customer = customer[0]
                    customer['hoadon_count'] = len(customer['hoadon']) if customer['hoadon'] else 0
            except Exception as e:
                logger.error(f"Lỗi khi tìm kiếm khách hàng với CCCD {cccd}: {str(e)}")
                flash('Lỗi khi tìm kiếm khách hàng!', 'error')

    try:
        customers = supabase.table('khachhang').select('*, hoadon(count)').execute().data or []
        for cust in customers:
            cust['hoadon_count'] = cust['hoadon']['count'] if cust['hoadon'] and 'count' in cust['hoadon'] else 0
        logger.info(f"Lấy danh sách khách hàng: {len(customers)} khách hàng")
        return render_template('employee/employee_customers.html', user=user, customers=customers, customer=customer)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách khách hàng: {str(e)}")
        flash('Lỗi khi lấy danh sách khách hàng!', 'error')
        return render_template('employee/employee_customers.html', user=user, customers=[], customer=None)

# Route cho tìm kiếm phòng (lễ tân)
@employee_bp.route('/search-room', methods=['GET', 'POST'])
@require_role('letan')
def search_room():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        checkin_date = request.form.get('checkin_date')
        checkout_date = request.form.get('checkout_date')

        if not (checkin_date and checkout_date):
            flash('Vui lòng nhập ngày nhận phòng và ngày trả phòng!', 'error')
            return redirect(url_for('employee.search_room'))

        try:
            checkin = datetime.strptime(checkin_date, '%Y-%m-%d')
            checkout = datetime.strptime(checkout_date, '%Y-%m-%d')
            if checkout <= checkin:
                flash('Ngày trả phòng phải sau ngày nhận phòng!', 'error')
                return redirect(url_for('employee.search_room'))

            rooms = get_available_rooms(checkin_date, checkout_date)
            logger.info(f"Tìm kiếm phòng từ {checkin_date} đến {checkout_date}: {len(rooms)} phòng khả dụng")
            return render_template('employee/employee_search_results.html', rooms=rooms, user=user, checkin_date=checkin_date, checkout_date=checkout_date)
        except ValueError as ve:
            logger.error(f"Lỗi định dạng ngày: {str(ve)}")
            flash('Định dạng ngày không hợp lệ! Vui lòng dùng YYYY-MM-DD.', 'error')
            return redirect(url_for('employee.search_room'))
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm phòng: {str(e)}")
            flash(f'Lỗi khi tìm kiếm phòng: {str(e)}', 'error')
            return redirect(url_for('employee.search_room'))

    return render_template('employee/employee_search_room.html', user=user)

# Route cho xác nhận check-in (lễ tân)
@employee_bp.route('/checkin', methods=['GET', 'POST'])
@require_role('letan')
def checkin():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'madatphong' not in data or 'action' not in data:
            return jsonify({"success": False, "message": "Dữ liệu gửi lên không hợp lệ!"}), 400

        try:
            madatphong = str(data.get('madatphong'))
            action = data.get('action')
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã đặt phòng hoặc hành động không hợp lệ!"}), 400

        if action != 'checkin':
            return jsonify({"success": False, "message": "Hành động không hợp lệ!"}), 400

        try:
            checkin_record = supabase.table('datphong')\
                .select('maphong, trangthai, ngaynhanphong')\
                .eq('madatphong', madatphong).single().execute().data
            if not checkin_record:
                return jsonify({"success": False, "message": "Đặt phòng không tồn tại!"}), 404

            maphong = checkin_record['maphong']
            current_status = checkin_record['trangthai']
            ngaynhanphong = checkin_record['ngaynhanphong']

            if current_status != 'Đã thanh toán':
                return jsonify({"success": False, "message": f"Đặt phòng #{madatphong} không thể check-in vì trạng thái hiện tại là '{current_status}'! Thanh toán trước khi check-in."}), 400

            # Kiểm tra xung đột đặt phòng
            conflicting_bookings = supabase.table('datphong')\
                .select('madatphong')\
                .eq('maphong', maphong)\
                .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])\
                .lte('ngaynhanphong', ngaynhanphong)\
                .gte('ngaytraphong', ngaynhanphong)\
                .neq('madatphong', madatphong)\
                .execute().data
            if conflicting_bookings:
                return jsonify({"success": False, "message": "Phòng đã được đặt trong khoảng thời gian này!"}), 400

            response1 = supabase.table('datphong')\
                .update({
                    'trangthai': 'Đã check-in',
                    'thoigiancheckindukien': datetime.now().isoformat()
                })\
                .eq('madatphong', madatphong).execute()
            response2 = supabase.table('phong')\
                .update({'trangthai': 'dang_su_dung'})\
                .eq('maphong', maphong).execute()
            if not response1.data or not response2.data:
                return jsonify({"success": False, "message": "Không thể cập nhật trạng thái check-in!"}), 500
            logger.info(f"Xác nhận check-in cho đặt phòng #{madatphong}")
            return jsonify({"success": True, "message": f"Đã xác nhận check-in cho đặt phòng #{madatphong}!"})
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận check-in #{madatphong}: {str(e)}")
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        checkins = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .eq('trangthai', 'Đã thanh toán')\
            .execute().data or []
        logger.info(f"Lấy danh sách đặt phòng đã thanh toán: {len(checkins)}")
        return render_template('employee/employee_checkin.html', user=user, checkins=checkins)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách đặt phòng đã thanh toán: {str(e)}")
        flash('Lỗi khi lấy danh sách đặt phòng!', 'error')
        return render_template('employee/employee_checkin.html', user=user, checkins=[])

# Route cho cập nhật trạng thái phòng (nhân viên dọn phòng)
@employee_bp.route('/update-room-status', methods=['GET', 'POST'])
@require_role('donphong')
def update_room_status():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            maphong = str(data.get('maphong'))
            new_status = data.get('trangthai')
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Dữ liệu không hợp lệ!"}), 400

        valid_statuses = ['trong', 'dang_bao_tri']
        if new_status not in valid_statuses:
            return jsonify({"success": False, "message": "Trạng thái không hợp lệ! Chọn: trong, dang_bao_tri"}), 400

        try:
            active_bookings = supabase.table('datphong')\
                .select('madatphong')\
                .eq('maphong', maphong)\
                .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])\
                .execute().data
            if active_bookings and new_status == 'trong':
                return jsonify({"success": False, "message": "Phòng đang được sử dụng, không thể đặt trạng thái 'trong'!"}), 400

            response = supabase.table('phong')\
                .update({'trangthai': new_status})\
                .eq('maphong', maphong).execute()
            if not response.data:
                return jsonify({"success": False, "message": "Không thể cập nhật trạng thái phòng!"}), 500
            logger.info(f"Cập nhật trạng thái phòng #{maphong} thành {new_status}")
            return jsonify({"success": True, "message": f"Đã cập nhật trạng thái phòng #{maphong} thành {new_status}!"})
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật trạng thái phòng #{maphong}: {str(e)}")
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        rooms = supabase.table('phong').select('*').eq('trangthai', 'dang_su_dung').execute().data or []
        logger.info(f"Lấy danh sách phòng đang sử dụng: {len(rooms)} phòng")
        return render_template('employee/employee_room_status.html', user=user, rooms=rooms)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách phòng: {str(e)}")
        flash('Lỗi khi lấy danh sách phòng!', 'error')
        return render_template('employee/employee_room_status.html', user=user, rooms=[])

# Route cho checkout
@employee_bp.route('/checkout', methods=['GET', 'POST'])
@require_role('letan')
def checkout():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'madatphong' not in data:
            return jsonify({"success": False, "message": "Dữ liệu gửi lên không hợp lệ!"}), 400

        try:
            madatphong = str(data.get('madatphong'))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Mã đặt phòng không hợp lệ!"}), 400

        try:
            booking = supabase.table('datphong')\
                .select('maphong, trangthai')\
                .eq('madatphong', madatphong)\
                .single().execute().data
            if not booking:
                return jsonify({"success": False, "message": "Đặt phòng không tồn tại!"}), 404

            if booking['trangthai'] != 'Đã check-in':
                return jsonify({"success": False, "message": f"Đặt phòng #{madatphong} không thể checkout vì trạng thái hiện tại là '{booking['trangthai']}'!"}), 400

            maphong = booking['maphong']

            # Kiểm tra dịch vụ chưa thanh toán
            unpaid_services = supabase.table('chitietdichvu')\
                .select('thanhtien')\
                .eq('madatphong', madatphong)\
                .eq('trangthaithanhtoan', 'Chưa thanh toán')\
                .execute().data or []
            if unpaid_services:
                return jsonify({"success": False, "message": "Vui lòng thanh toán các dịch vụ trước khi checkout!"}), 400

            response1 = supabase.table('datphong')\
                .update({
                    'trangthai': 'Đã trả phòng',
                    'ngaytraphongthucte': datetime.now().isoformat()
                })\
                .eq('madatphong', madatphong).execute()

            response2 = supabase.table('phong')\
                .update({'trangthai': 'trong'})\
                .eq('maphong', maphong).execute()

            if not response1.data or not response2.data:
                return jsonify({"success": False, "message": "Không thể cập nhật trạng thái checkout!"}), 500

            invoice = get_invoice_by_booking_id(madatphong)
            if invoice:
                services = supabase.table('chitietdichvu')\
                    .select('thanhtien')\
                    .eq('madatphong', madatphong)\
                    .execute().data or []
                total_service_cost = sum(item['thanhtien'] for item in services if item['thanhtien'])
                if total_service_cost > 0:
                    supabase.table('hoadon')\
                        .update({'tongtien_dichvu': total_service_cost})\
                        .eq('mahoadon', invoice['mahoadon']).execute()

            logger.info(f"Hoàn tất checkout cho đặt phòng #{madatphong}")
            return jsonify({"success": True, "message": f"Đã hoàn tất checkout cho đặt phòng #{madatphong}!"})
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận checkout #{madatphong}: {str(e)}")
            return jsonify({"success": False, "message": f"Lỗi: {str(e)}"}), 500

    try:
        checkouts = supabase.table('datphong')\
            .select('*, khachhang(hoten, sodienthoai), phong(maphong, loaiphong)')\
            .eq('trangthai', 'Đã check-in')\
            .execute().data or []
        logger.info(f"Lấy danh sách đặt phòng đã check-in: {len(checkouts)}")
        return render_template('employee/employee_checkout.html', user=user, checkouts=checkouts)
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách đặt phòng đã check-in: {str(e)}")
        flash('Lỗi khi lấy danh sách đặt phòng!', 'error')
        return render_template('employee/employee_checkout.html', user=user, checkouts=[])

# Route cho dashboard chung
@employee_bp.route('/dashboard')
@require_role('letan', 'ketoan', 'donphong')
def employee_dashboard():
    user = session.get('user')
    role = user.get('role')
    if role == 'letan':
        return redirect(url_for('employee.letan_dashboard'))
    elif role == 'ketoan':
        return redirect(url_for('employee.ketoan_dashboard'))
    elif role == 'donphong':
        return redirect(url_for('employee.update_room_status'))
    flash('Vai trò không hợp lệ!', 'error')
    session.pop('user', None)
    return redirect(url_for('admin.admin_login'))

# Route cho đặt phòng
@employee_bp.route('/book_room', methods=['GET', 'POST'])
@require_role('letan')
def book_room():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    
    if request.method == 'POST':
        maphong = request.form.get('maphong')
        checkin_date = request.form.get('checkin_date')
        checkout_date = request.form.get('checkout_date')
        hoten = request.form.get('hoten')
        sodienthoai = request.form.get('sodienthoai')
        quoctich = request.form.get('quoctich', 'Việt Nam')
        gioitinh = request.form.get('gioitinh')
        ngaysinh = request.form.get('ngaysinh')
        diachi = request.form.get('diachi')
        cccd = request.form.get('cccd')
        songuoi = request.form.get('songuoi', 1, type=int)
        thoigiancheckindukien = request.form.get('thoigiancheckindukien')
        yeucaudacbiet = request.form.get('yeucaudacbiet')

        required_fields = [maphong, checkin_date, checkout_date, hoten, sodienthoai, cccd]
        if not all(required_fields):
            flash('Vui lòng nhập đầy đủ thông tin bắt buộc!', 'error')
            return redirect(url_for('employee.search_room'))

        try:
            checkin = datetime.strptime(checkin_date, '%Y-%m-%d')
            checkout = datetime.strptime(checkout_date, '%Y-%m-%d')
            if checkout <= checkin:
                flash('Ngày trả phòng phải sau ngày nhận phòng!', 'error')
                return redirect(url_for('employee.search_room'))

            # Kiểm tra trạng thái phòng
            room = supabase.table("phong").select("giaphong, trangthai, succhua").eq("maphong", maphong).single().execute().data
            if not room or room['trangthai'] != 'trong':
                flash('Phòng không khả dụng để đặt!', 'error')
                return redirect(url_for('employee.search_room'))

            if songuoi > room['succhua']:
                flash(f'Số người ({songuoi}) vượt quá sức chứa của phòng ({room["succhua"]})!', 'error')
                return redirect(url_for('employee.search_room'))

            # Kiểm tra xem phòng có đặt phòng chồng lấn không
            conflicting_bookings = supabase.table('datphong')\
                .select('madatphong')\
                .eq('maphong', maphong)\
                .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])\
                .lte('ngaynhanphong', checkout_date)\
                .gte('ngaytraphong', checkin_date)\
                .execute().data
            if conflicting_bookings:
                flash('Phòng đã được đặt trong khoảng thời gian này!', 'error')
                return redirect(url_for('employee.search_room'))

            days = (checkout - checkin).days
            tongtien = room['giaphong'] * days

            # Chèn dữ liệu vào bảng khachhang
            khachhang_data = {
                'hoten': hoten,
                'sodienthoai': sodienthoai,
                'cccd': cccd,
                'quoctich': quoctich,
                'gioitinh': gioitinh,
                'ngaysinh': ngaysinh,
                'diachi': diachi,
                'ngaytao': datetime.now().isoformat()
            }
            existing = supabase.table("khachhang").select("makhachhang").eq("cccd", cccd).execute()
            if existing.data:
                makhachhang = existing.data[0]['makhachhang']
            else:
                result = supabase.table("khachhang").insert(khachhang_data).execute()
                makhachhang = result.data[0]['makhachhang']

            # Chuẩn bị dữ liệu đặt phòng
            booking_data = {
                'maphong': int(maphong),
                'ngaynhanphong': checkin_date,
                'ngaytraphong': checkout_date,
                'songuoi': songuoi,
                'tongtien': float(tongtien),
                'trangthai': 'Chờ xác nhận',
                'thoigiancheckindukien': thoigiancheckindukien if thoigiancheckindukien else None,
                'yeucaudacbiet': yeucaudacbiet,
                'makhachhang': makhachhang,
                'thoigiandat': datetime.now().isoformat()
            }
            new_booking = insert_booking(booking_data)
            if not new_booking:
                raise Exception("Không thể tạo đặt phòng!")
            logger.info(f"Đặt phòng mới #{new_booking.get('madatphong')} cho phòng #{maphong}")
            flash('Đặt phòng thành công với trạng thái Chờ xác nhận!', 'success')
            return render_template('employee/employee_book_room.html', 
                                 user=user, 
                                 maphong=maphong, 
                                 checkin_date=checkin_date, 
                                 checkout_date=checkout_date)
        except ValueError as ve:
            logger.error(f"Lỗi định dạng hoặc dữ liệu: {str(ve)}")
            flash(str(ve), 'error')
            return redirect(url_for('employee.search_room'))
        except Exception as e:
            logger.error(f"Lỗi khi đặt phòng: {str(e)}")
            flash(f'Lỗi khi đặt phòng: {str(e)}', 'error')
            return redirect(url_for('employee.search_room'))

    maphong = request.args.get('maphong')
    checkin_date = request.args.get('checkin_date')
    checkout_date = request.args.get('checkout_date')
    return render_template('employee/employee_book_room.html', user=user, maphong=maphong, checkin_date=checkin_date, checkout_date=checkout_date)


@employee_bp.route('/auto-checkout', methods=['GET', 'POST'])
@require_role('letan')
def employee_auto_checkout():
    user = session.get('user')
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    today = datetime.now().date().isoformat()

    try:
        # Lấy danh sách phòng quá hạn (ngày trả nhỏ hơn hôm nay)
        expired_bookings = (
            supabase.table("datphong")
            .select("madatphong, maphong, ngaynhanphong, ngaytraphong, trangthai, tongtien, khachhang(hoten), phong(loaiphong)")
            .lt("ngaytraphong", today)
            .neq("trangthai", "Đã trả phòng")
            .neq("trangthai", "Đã hủy")
            .execute()
            .data
        )

        if request.method == 'POST':
            selected = request.form.getlist('selected_ids')
            if not selected:
                flash("Vui lòng chọn ít nhất một đặt phòng để trả!", "warning")
                return redirect(url_for('employee.employee_auto_checkout'))

            count = 0
            for madatphong in selected:
                try:
                    booking = next((b for b in expired_bookings if str(b['madatphong']) == madatphong), None)
                    if not booking:
                        continue

                    # Cập nhật trạng thái đặt phòng
                    supabase.table("datphong").update({
                        "trangthai": "Đã trả phòng",
                        "ngaytraphongthucte": datetime.now().isoformat()
                    }).eq("madatphong", madatphong).execute()

                    # Cập nhật trạng thái phòng
                    supabase.table("phong").update({
                        "trangthai": "trong"
                    }).eq("maphong", booking["maphong"]).execute()

                    count += 1
                    logger.info(f"Auto checkout thành công: Phòng {booking['maphong']} (Đơn #{madatphong})")
                except Exception as ex:
                    logger.error(f"Lỗi auto checkout đơn #{madatphong}: {ex}")

            flash(f"Đã tự động checkout {count} phòng quá hạn!", "success")
            return redirect(url_for('employee.employee_auto_checkout'))

        return render_template(
            'employee/employee_auto_checkout.html',
            user=user,
            expired_bookings=expired_bookings,
            today=today
        )
    except Exception as e:
        logger.error(f"Lỗi khi tải danh sách auto checkout: {e}", exc_info=True)
        flash("Không thể tải danh sách phòng quá hạn!", "error")
        return render_template('employee/employee_auto_checkout.html', user=user, expired_bookings=[])