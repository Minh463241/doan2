from flask import Blueprint, make_response, render_template, request, redirect, url_for, flash, session
from config import supabase
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_mail import Mail, Message
import random, string

auth = Blueprint("auth", __name__)
mail = Mail()  # Khởi tạo Flask-Mail

# ---------------------- ĐĂNG NHẬP ----------------------
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('matkhau')

        if not email or not password:
            flash("Vui lòng nhập đầy đủ email và mật khẩu.", "danger")
            return render_template('login.html')

        user_response = supabase.table("khachhang").select("*").eq("email", email).execute()
        user = user_response.data[0] if user_response.data else None

        if user and user.get('matkhau') == password:
            access_token = create_access_token(identity=str(user.get('makhachhang')))
            response = make_response(redirect(url_for('index')))
            response.set_cookie('access_token_cookie', access_token, httponly=True, samesite='Lax')
            session['user'] = {
                "makhachhang": user.get('makhachhang'),
                "hoten": user.get('hoten'),
                "email": user.get('email'),
                "id": user.get('makhachhang')
            }
            flash('Đăng nhập thành công!', 'success')
            return response
        else:
            flash('Email hoặc mật khẩu không đúng.', 'danger')

    return render_template('login.html')


# ---------------------- ĐĂNG XUẤT ----------------------
@auth.route('/logout')
def logout():
    session.pop('user', None)
    flash("Đã đăng xuất.", "success")

    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('access_token_cookie')
    return response


# ---------------------- ĐĂNG KÝ ----------------------
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = {
            "hoten": request.form.get('hoten'),
            "sodienthoai": request.form.get('sodienthoai'),
            "email": request.form.get('email'),
            "cccd": request.form.get('cccd'),
            "diachi": request.form.get('diachi'),
            "ngaysinh": request.form.get('ngaysinh'),
            "gioitinh": request.form.get('gioitinh'),
            "quoctich": request.form.get('quoctich'),
            "ghichu": "",
            "avatar": "",
            "matkhau": request.form.get('matkhau'),
        }

        if not all([data["hoten"], data["sodienthoai"], data["email"], data["matkhau"]]):
            flash("Vui lòng nhập đầy đủ thông tin bắt buộc.", "danger")
            return redirect(url_for('auth.register'))

        existing_response = supabase.table("khachhang").select("sodienthoai").eq("sodienthoai", data["sodienthoai"]).execute()
        existing = existing_response.data[0] if existing_response.data else None

        if existing and existing.get('sodienthoai') == data["sodienthoai"]:
            flash("Số điện thoại đã được đăng ký.", "danger")
            return redirect(url_for('auth.register'))

        result_response = supabase.table("khachhang").insert(data).execute()
        if result_response.data:
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Đăng ký thất bại.", "danger")

    return render_template('register.html')


# ---------------------- KHỞI TẠO MAIL ----------------------
@auth.record_once
def on_load(state):
    app = state.app
    mail.init_app(app)


# ---------------------- QUÊN MẬT KHẨU ----------------------
@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        # Kiểm tra email có tồn tại không
        user_response = supabase.table("khachhang").select("hoten").eq("email", email).execute()
        if not user_response.data:
            flash("Email không tồn tại trong hệ thống.", "danger")
            return render_template('forgot_password.html')

        user_name = user_response.data[0]['hoten']

        # Tạo mật khẩu mới ngẫu nhiên
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        # Cập nhật mật khẩu trong Supabase
        try:
            supabase.table("khachhang").update({"matkhau": new_password}).eq("email", email).execute()
        except Exception as e:
            flash(f"Lỗi cập nhật mật khẩu: {e}", "danger")
            return render_template('forgot_password.html')

        # Gửi mail cho người dùng
        try:
            msg = Message(
                subject="🔑 Mật khẩu mới của bạn - KeiWei Hotel",
                recipients=[email],
                body=f"Xin chào {user_name},\n\nHệ thống đã tạo mật khẩu mới cho bạn:\n👉 Mật khẩu mới: {new_password}\n\nVui lòng đăng nhập và đổi lại mật khẩu sau khi vào hệ thống.\n\nTrân trọng,\nKeiWei Hotel"
            )
            mail.send(msg)
            flash("Mật khẩu mới đã được gửi đến email của bạn.", "success")
        except Exception as e:
            flash(f"Lỗi khi gửi mail: {e}", "danger")

        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


# ---------------------- TRANG CÁ NHÂN ----------------------
@auth.route('/profile')
@jwt_required()
def profile():
    identity = get_jwt_identity()

    user = session.get('user')
    if not user or user.get('makhachhang') != identity:
        user_response = supabase.table("khachhang").select("*").eq("makhachhang", identity).execute()
        user = user_response.data[0] if user_response.data else None
        if user:
            session['user'] = {
                "makhachhang": user.get('makhachhang'),
                "hoten": user.get('hoten'),
                "email": user.get('email'),
                "id": user.get('makhachhang')
            }
        else:
            flash('Không tìm thấy người dùng.', 'danger')
            return redirect(url_for('auth.login'))

    return render_template('profile.html', user=user)
