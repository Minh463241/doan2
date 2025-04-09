from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_supabase import get_user_by_email, get_user_by_phone, insert_user

auth = Blueprint("auth", __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['matkhau']
        except KeyError as e:
            flash(f"Thiếu trường {e.args[0]} trong form.", "danger")
            return render_template('login.html')

        user = get_user_by_email(email)
        if user and user['matkhau'] == password:
            session['user'] = {
                "id": user['makhachhang'],
                "hoten": user['hoten'],
                "email": user['email']
            }
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email hoặc mật khẩu không đúng.', 'danger')

    return render_template('login.html')


@auth.route('/logout')
def logout():
    session.pop('user', None)
    flash("Đã đăng xuất.", "success")
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = {
            "hoten": request.form['hoten'],
            "sodienthoai": request.form['sodienthoai'],
            "email": request.form['email'],
            "cccd": request.form['cccd'],
            "diachi": request.form['diachi'],
            "ngaysinh": request.form['ngaysinh'],
            "gioitinh": request.form['gioitinh'],
            "quoctich": request.form['quoctich'],
            "ghichu": "",
            "avatar": "",
            "matkhau": request.form['matkhau'],
        }

        existing = get_user_by_phone(data["sodienthoai"])
        if existing and existing.data:
            flash("Số điện thoại đã được đăng ký.", "danger")
            return redirect(url_for('auth.register'))

        result = insert_user(data)
        if result.data:
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Đăng ký thất bại.", "danger")

    return render_template('register.html')
