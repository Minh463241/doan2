from flask import Flask, render_template, session
from routes.booking import booking_bp
from routes.payment import payment_bp

from routes.auth import auth
from routes.room import room_bp
from routes.admin import admin_bp
from routes.manager import manager_bp
from routes.employee import employee_bp
from utils.db_supabase import supabase
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey123")

# Register Blueprints
app.register_blueprint(booking_bp, url_prefix='/booking')
app.register_blueprint(payment_bp, url_prefix='/payment')

app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(room_bp, url_prefix='/room')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(manager_bp, url_prefix='/manager')
app.register_blueprint(employee_bp, url_prefix='/employee')

@app.route('/')
def index():
    user = session.get("user")
    try:
        # Lấy danh sách phòng có trạng thái "Trống"
        response = supabase.table("phong").select("*").eq("trangthai", "Trống").limit(6).execute()
        rooms = response.data if response.data else []

        # Lấy số lượng đặt phòng cho từng phòng từ bảng datphong
        booking_counts_response = supabase.table("datphong").select("maphong").execute()
        booking_counts = {}
        for booking in booking_counts_response.data:
            maphong = booking['maphong']
            booking_counts[maphong] = booking_counts.get(maphong, 0) + 1

        # Thêm số lượng đặt phòng vào dữ liệu phòng và sắp xếp
        for room in rooms:
            room['booking_count'] = booking_counts.get(room['maphong'], 0)  # Mặc định là 0 nếu không có lượt đặt
            # Đảm bảo giaphong là số
            if room['giaphong'] is not None:
                try:
                    room['giaphong'] = float(room['giaphong'])
                except (ValueError, TypeError):
                    room['giaphong'] = None
        rooms = sorted(rooms, key=lambda x: x['booking_count'], reverse=True)

    except Exception as e:
        print("❌ Lỗi khi lấy phòng nổi bật:", e)
        rooms = []

    return render_template('index.html', user=user, rooms=rooms)

if __name__ == "__main__":
    app.run(debug=True)
