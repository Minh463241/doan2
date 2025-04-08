# routes/room.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_supabase import supabase
from utils.upload_cloudinary import upload_image_to_cloudinary

room_bp = Blueprint('room', __name__)

@room_bp.route('/add', methods=['GET', 'POST'])
def add_room():
    if request.method == 'POST':
        # Lấy dữ liệu từ form (bỏ maphong vì để tự tăng)
        loaiphong  = request.form.get('loaiphong')
        giaphong   = request.form.get('giaphong')
        succhua    = request.form.get('succhua')
        trangthai  = request.form.get('trangthai')
        dientich   = request.form.get('dientich')
        file_image = request.files.get('hinhanh')

        hinhanh_url = None
        if file_image:
            hinhanh_url = upload_image_to_cloudinary(file_image)

        data = {
    "loaiphong": loaiphong,
    "giaphong": float(giaphong) if giaphong else None,
    "succhua": int(float(succhua)) if succhua else None,
    "trangthai": trangthai,
    "hinhanh": hinhanh_url,
     "dientich": int(float(dientich)) if dientich else None,
}


        try:
            response = supabase.table("phong").insert(data).execute()
            if response.data:
                flash("Thêm phòng thành công!", "success")
            else:
                flash("Không có dữ liệu trả về từ Supabase.", "warning")
        except Exception as e:
            flash(f"Lỗi khi thêm phòng: {e}", "error")

        return redirect(url_for('room.add_room'))

    return render_template("room_add.html")

@room_bp.route('/list', methods=['GET'])
def room_list():
    response = supabase.table("phong").select("*").execute()
    rooms = response.data if response.data else []
    return render_template("room_list.html", rooms=rooms)
