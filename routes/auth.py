from flask import Blueprint, make_response, render_template, request, redirect, url_for, flash, session
from config import supabase
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

auth = Blueprint("auth", __name__)

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

@auth.route('/logout')
def logout():
    session.pop('user', None)
    flash("Đã đăng xuất.", "success")

    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('access_token_cookie')  # Xóa token JWT khỏi cookie
    return response


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
        result = {"success": bool(result_response.data)} if result_response.data else {"success": False}

        if result.get('success', False):
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Đăng ký thất bại.", "danger")

    return render_template('register.html')


@auth.route('/profile')
@jwt_required()
def profile():
    identity = get_jwt_identity()  # Lấy makhachhang từ token

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
