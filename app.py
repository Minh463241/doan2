from flask import Flask, render_template, session
from flask_jwt_extended import JWTManager
from routes.booking import booking_bp
from routes.payment import payment_bp
from routes.auth import auth
from routes.room import room_bp
from routes.admin import admin_bp
from routes.manager import manager_bp
from routes.employee import employee_bp
from routes.book_service import customer_service_bp  # Thêm import cho book_service
from config import Config, supabase
import bcrypt


app = Flask(__name__, template_folder='templates', static_folder='static')

# Áp dụng cấu hình từ config.py
app.config.from_object(Config)

# Cấu hình JWT nhận token từ cookie
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'  # Đặt rõ tên cookie token
app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Tạm thời tắt CSRF để test

jwt = JWTManager(app)

# Register Blueprints
app.register_blueprint(booking_bp, url_prefix='/booking')
app.register_blueprint(payment_bp, url_prefix='/payment')
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(room_bp, url_prefix='/room')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(manager_bp, url_prefix='/manager')
app.register_blueprint(employee_bp, url_prefix='/employee')
app.register_blueprint(customer_service_bp, url_prefix='/customer/service')  # Đăng ký Blueprint mới

# Định nghĩa bộ lọc format_price
def format_price(value):
    try:
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except (ValueError, TypeError):
        return value
app.jinja_env.filters['format_price'] = format_price
@app.route('/')
def index():
    user = session.get("user")
    try:
        # Lấy tất cả phòng
        response = supabase.table("phong").select("maphong, loaiphong, giaphong, succhua, dientich, hinhanh").execute()
        all_rooms = response.data if response.data else []
        print(f"Đã lấy {len(all_rooms)} phòng từ bảng phong: {all_rooms[:5]}")  # In 5 phòng đầu tiên để debug

        if not all_rooms:
            print("Không có phòng nào trong bảng phong")
            rooms = []
        else:
            # Tính số lượt đặt phòng (chỉ các trạng thái hợp lệ)
            booking_counts_response = supabase.table("datphong").select("maphong")\
                .in_("trangthai", ["Đã xác nhận", "Đã thanh toán", "Đã check-in"])\
                .execute()
            booking_counts_data = booking_counts_response.data if booking_counts_response.data else []
            booking_counts = {}
            for booking in booking_counts_data:
                maphong = booking['maphong']
                booking_counts[maphong] = booking_counts.get(maphong, 0) + 1
            print(f"Đã tính {len(booking_counts)} lượt đặt từ bảng datphong: {booking_counts}")

            # Gộp số lượt đặt theo loại phòng (loaiphong)
            type_counts = {}
            room_by_type = {}
            for room in all_rooms:
                loaiphong = room.get('loaiphong', 'Unknown')  # Xử lý trường hợp loaiphong rỗng
                count = booking_counts.get(room['maphong'], 0)
                if loaiphong and loaiphong != 'Unknown':
                    if loaiphong not in type_counts:
                        type_counts[loaiphong] = 0
                        room_by_type[loaiphong] = room  # Lưu phòng đầu tiên của loại phòng
                    type_counts[loaiphong] += count
            print(f"Đã gộp {len(type_counts)} loại phòng với số lượt: {type_counts}")

            # Sắp xếp các loại phòng theo số lượt đặt (giảm dần)
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)

            # Tạo danh sách phòng đại diện cho từng loại phòng
            rooms = []
            for loaiphong, total_count in sorted_types[:3]:  # Lấy 3 loại phòng đầu tiên
                if loaiphong in room_by_type:
                    room = room_by_type[loaiphong]
                    room['booking_count'] = total_count  # Số lượt đặt của toàn bộ loại phòng
                    if room['giaphong'] is not None:
                        try:
                            room['giaphong'] = float(room['giaphong'])
                        except (ValueError, TypeError):
                            room['giaphong'] = None
                    rooms.append(room)
            print(f"Đã tạo danh sách rooms với {len(rooms)} loại phòng: {[r['loaiphong'] for r in rooms]}")

    except Exception as e:
        print("❌ Lỗi khi lấy loại phòng nổi bật:", str(e))
        rooms = []

    return render_template('index.html', user=user, rooms=rooms)

@app.template_filter('format_currency')
def format_currency(value):
    if value is None or value == 0:
        return "0 VND"
    return "{:,.0f}".format(float(value)).replace(",", ".") + " VND"

if __name__ == "__main__":
    app.run(debug=True)
