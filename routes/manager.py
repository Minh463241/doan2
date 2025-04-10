from flask import Blueprint, render_template, session
from utils.db_supabase import (
    get_all_employees, get_rooms, get_total_bookings,
    get_total_employees, get_total_revenue, supabase
)

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")

@manager_bp.route("/dashboard")
def dashboard():
    # Lấy thống kê
    total_employees = len(get_total_employees().data)
    total_bookings = len(get_total_bookings().data)
    total_revenue = get_total_revenue()

    # Lấy danh sách phòng và nhân viên
    rooms = get_rooms().data
    employees = get_all_employees().data

    # Lấy danh sách hóa đơn đã thanh toán
    hoadon_res = supabase.table("hoadon").select("*").eq("trangthai", "đã thanh toán").execute()
    hoadon_list = hoadon_res.data

    # Gắn tên khách hàng vào hóa đơn
    for hd in hoadon_list:
        ma_kh = hd.get("makhachhang")
        if ma_kh:
            kh_res = supabase.table("khachhang").select("hoten").eq("makhachhang", ma_kh).single().execute()
            hd["tenkhachhang"] = kh_res.data["hoten"] if kh_res.data else "Không rõ"
        else:
            hd["tenkhachhang"] = "Không rõ"

    return render_template("manager/manager_dashboard.html",
                       total_employees=total_employees,
                       total_bookings=total_bookings,
                       total_revenue=total_revenue,
                       rooms=rooms,
                       employees=employees,
                       hoadon_list=hoadon_list,
                       user=session.get("user"))
