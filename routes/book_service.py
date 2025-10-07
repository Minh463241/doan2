from flask import Blueprint, request, render_template, session, flash, redirect, url_for
from supabase import create_client, Client
from config import Config
from datetime import datetime
import logging
from utils.db_supabase import (
    get_all_services,
    get_service_by_id,
    get_invoice_by_booking_id,
    update_invoice_with_service
)

# Cấu hình logging
logging.basicConfig(level=logging.ERROR, filename='booking.log', filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Blueprint cho chức năng khách hàng đặt dịch vụ
customer_service_bp = Blueprint('customer_service', __name__)

# Tạo client Supabase
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

@customer_service_bp.route('/book', methods=['GET'])
def show_booking_form():
    # Kiểm tra đăng nhập
    if 'user' not in session or 'makhachhang' not in session.get('user', {}):
        flash("Vui lòng đăng nhập để đặt dịch vụ!", "danger")
        return redirect(url_for('auth.login'))

    makhachhang = session['user']['makhachhang']
    
    # Lấy tất cả đặt phòng hợp lệ của khách hàng
    bookings = get_bookings(makhachhang)
    if not bookings:
        logger.warning(f"Khách hàng {makhachhang} không có đặt phòng hợp lệ.")
        return render_template('book_service.html', error="Bạn chưa có đặt phòng hợp lệ!", bookings=bookings)

    # Lấy danh sách dịch vụ
    services = get_all_services()
    if not services:
        logger.error("Không thể tải danh sách dịch vụ.")
        return render_template('book_service.html', error="Không thể tải dịch vụ!", bookings=bookings)

    # Kiểm tra và chuẩn hóa dữ liệu dịch vụ
    for service in services:
        if 'hinhanh' not in service or not service['hinhanh']:
            service['hinhanh'] = None
        if 'giadichvu' not in service or not service['giadichvu']:
            logger.warning(f"Dịch vụ {service.get('madichvu')} thiếu giá dịch vụ, đặt mặc định 0.")
            service['giadichvu'] = 0
        if 'tendichvu' not in service or not service['tendichvu']:
            logger.warning(f"Dịch vụ {service.get('madichvu')} thiếu tên, đặt mặc định 'Không có tên'.")
            service['tendichvu'] = 'Không có tên'

    # Truyền thông tin vào template
    return render_template('book_service.html', 
        services=services, 
        makhachhang=makhachhang, 
        bookings=bookings
    )

@customer_service_bp.route('/book', methods=['POST'])
def book_service():
    try:
        data = request.form
        madatphong = data.get('madatphong')
        madichvu = data.get('madichvu')
        soluong = int(data.get('soluong', 1))

        if 'user' not in session or 'makhachhang' not in session.get('user', {}):
            flash("Vui lòng đăng nhập để đặt dịch vụ!", "danger")
            return redirect(url_for('auth.login'))
        makhachhang = session['user']['makhachhang']

        logger.info(f"Nhận dữ liệu từ form: madatphong={madatphong}, madichvu={madichvu}, soluong={soluong}, makhachhang={makhachhang}")

        if not (madatphong and madichvu):
            logger.error("Thiếu thông tin bắt buộc trong form.")
            return render_template('book_service.html', 
                error="Thiếu thông tin bắt buộc!", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 400

        if soluong <= 0:
            logger.error("Số lượng không hợp lệ.")
            return render_template('book_service.html', 
                error="Số lượng phải lớn hơn 0.", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 400

        # Kiểm tra đặt phòng
        booking_resp = supabase.table('datphong')\
            .select('makhachhang, trangthai, maphong, tongtien')\
            .eq('madatphong', madatphong)\
            .single().execute()

        if hasattr(booking_resp, 'error') and booking_resp.error:
            logger.error(f"Lỗi truy vấn đặt phòng: {booking_resp.error.message if booking_resp.error else 'Không xác định'}")
            return render_template('book_service.html', 
                error="Không thể truy vấn thông tin đặt phòng!", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 500
        elif not booking_resp.data:
            logger.error(f"Đặt phòng không tồn tại: madatphong={madatphong}")
            return render_template('book_service.html', 
                error="Đặt phòng không tồn tại!", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 404
        else:
            booking = booking_resp.data

        if booking['makhachhang'] != makhachhang:
            logger.error(f"Khách hàng không có quyền: makhachhang={makhachhang}, madatphong={madatphong}, makhachhang của đặt phòng={booking['makhachhang']}")
            return render_template('book_service.html', 
                error=f"Bạn không có quyền thêm dịch vụ cho đặt phòng này! Đặt phòng thuộc về khách hàng khác (ID: {booking['makhachhang']}).", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 403

        if booking['trangthai'] not in ['Đã xác nhận', 'Đã thanh toán', 'Đã check-in']:
            logger.error(f"Trạng thái đặt phòng không hợp lệ: trangthai={booking['trangthai']}")
            return render_template('book_service.html', 
                error=f"Trạng thái đặt phòng hiện tại không hợp lệ: {booking['trangthai']}.", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 400

        # Kiểm tra hóa đơn
        invoice = get_invoice_by_booking_id(madatphong)
        if not invoice:
            logger.error(f"Hóa đơn không tồn tại cho đặt phòng: madatphong={madatphong}")
            return render_template('book_service.html', 
                error="Hóa đơn chưa được tạo!", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 404

        # Kiểm tra dịch vụ
        service = get_service_by_id(madichvu)
        if not service:
            logger.error(f"Dịch vụ không tồn tại: madichvu={madichvu}")
            return render_template('book_service.html', 
                error="Dịch vụ không tồn tại!", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 404

        thanhtien = service['giadichvu'] * soluong

        # Ghi vào bảng chi tiết dịch vụ
        service_detail = {
            'madatphong': madatphong,
            'madichvu': madichvu,
            'soluong': soluong,
            'thanhtien': thanhtien,
            'ngaydat': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'trangthai': 'Chưa thanh toán'
        }
        response = supabase.table('chitietdichvu').insert(service_detail).execute()

        if hasattr(response, 'error') and response.error:
            logger.error(f"Lỗi thêm dịch vụ: {response.error.message if response.error else 'Không xác định'}")
            return render_template('book_service.html', 
                error="Không thể thêm dịch vụ!", 
                makhachhang=makhachhang, 
                bookings=get_bookings(makhachhang)), 500

        # Cập nhật hóa đơn với chi phí dịch vụ
        update_invoice_with_service(madatphong, thanhtien)

        # Lấy tổng tiền mới từ hóa đơn hoặc tính lại
        invoice = get_invoice_by_booking_id(madatphong)
        if invoice and 'tongtien' in invoice:
            tongtien = float(invoice['tongtien'])
        else:
            logger.error(f"Không thể lấy tổng tiền từ hóa đơn: madatphong={madatphong}")
            tongtien = float(booking['tongtien']) + thanhtien  # Tính tạm nếu không lấy được từ hóa đơn

        # Lưu thông tin vào session để chuyển sang thanh toán
        session['booking'] = {
            'madatphong': madatphong,
            'maphong': booking['maphong'],
            'ngaynhanphong': booking.get('ngaynhanphong', ''),
            'ngaytraphong': booking.get('ngaytraphong', ''),
            'tongtien': tongtien,
            'makhachhang': makhachhang
        }

        logger.info(f"Đặt dịch vụ thành công, chuyển sang thanh toán: madatphong={madatphong}, tongtien={tongtien}")

        # Chuyển hướng đến trang thanh toán PayPal
        return redirect(url_for('payment.pay'))

    except (ValueError, TypeError) as e:
        logger.error("Lỗi dữ liệu đầu vào:", exc_info=True)
        return render_template('book_service.html', error=str(e), makhachhang=makhachhang, bookings=get_bookings(makhachhang)), 400

    except Exception as e:
        logger.error(f"Lỗi hệ thống: {str(e)}", exc_info=True)
        return render_template('book_service.html', error=f"Lỗi hệ thống: {str(e)}", makhachhang=makhachhang, bookings=get_bookings(makhachhang)), 500

# Hàm phụ để lấy danh sách đặt phòng
def get_bookings(makhachhang):
    try:
        booking_resp = supabase.table('datphong')\
            .select('madatphong, maphong, trangthai')\
            .eq('makhachhang', makhachhang)\
            .in_('trangthai', ['Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])\
            .order('ngaynhanphong', desc=True)\
            .execute()
        
        if hasattr(booking_resp, 'error') and booking_resp.error:
            logger.error(f"Lỗi khi lấy danh sách đặt phòng: {booking_resp.error.message if booking_resp.error else 'Không xác định'}")
            return []
        return booking_resp.data if booking_resp.data else []
    except Exception as e:
        logger.error(f"Lỗi hệ thống khi lấy danh sách đặt phòng: {str(e)}")
        return []