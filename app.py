from flask import Flask, render_template, session
from routes.booking import booking_bp
from routes.payment import payment_bp
from routes.upload import upload_bp
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
app.register_blueprint(upload_bp, url_prefix='/upload')
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(room_bp, url_prefix='/room')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(manager_bp, url_prefix='/manager')
app.register_blueprint(employee_bp, url_prefix='/employee')

@app.route('/')
def index():
    user = session.get("user")
    try:
        # Lấy danh sách phòng nổi bật với trạng thái là số (ví dụ: 0) hoặc giá trị tương ứng, hãy đảm bảo khớp với DB của bạn
        response = supabase.table("phong").select("*").eq("trangthai", 0).limit(6).execute()
        rooms = response.data if response.data else []
    except Exception as e:
        print("❌ Lỗi khi lấy phòng nổi bật:", e)
        rooms = []
    return render_template('index.html', user=user, rooms=rooms)

if __name__ == "__main__":
    app.run(debug=True)
