from flask import Flask, render_template, session
from routes.booking import booking_bp
from routes.payment import payment_bp
from routes.upload import upload_bp
from routes.auth import auth
from routes.room import room_bp  # Đừng quên nếu bạn dùng route phòng
from utils.db_supabase import supabase  # ✅ Thêm dòng này

import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey123")

# Đăng ký Blueprint
app.register_blueprint(booking_bp, url_prefix='/booking')
app.register_blueprint(payment_bp, url_prefix='/payment')
app.register_blueprint(upload_bp, url_prefix='/upload')
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(room_bp, url_prefix='/room')  # ✅ Nếu có route room

@app.route('/')
def index():
    user = session.get("user")

    try:
        # ✅ Lấy 6 phòng đầu tiên từ Supabase
        response = supabase.table("phong").select("*").limit(6).execute()
        rooms = response.data if response.data else []
    except Exception as e:
        print("❌ Lỗi khi lấy phòng nổi bật:", e)
        rooms = []

    return render_template('index.html', user=user, rooms=rooms)

if __name__ == "__main__":
    app.run(debug=True)
