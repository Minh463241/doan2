from supabase import create_client, Client
from config import Config

supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

def insert_booking(data):
    return supabase.table("datphong").insert(data).execute()

def update_payment_status(ma_hoa_don, transaction_id):
    return supabase.table("hoadon").update({
        "trangthai": "đã thanh toán",
        "magiaodichpaypal": transaction_id
    }).eq("mahoadon", ma_hoa_don).execute()

def get_rooms():
    return supabase.table("phong").select("*").execute()

def insert_user(data):
    return supabase.table("khachhang").insert(data).execute()

def get_user_by_phone(phone):
    return supabase.table("khachhang").select("*").eq("sodienthoai", phone).execute()

# ----------- NHÂN VIÊN (nhanvien) -----------
def get_all_employees():
    return supabase.table("nhanvien").select("*").execute()

def get_user_by_email(email):
    res = supabase.table("khachhang").select("*").eq("email", email).execute()
    return res.data[0] if res.data else None

def get_admin_by_email(email):
    res = supabase.table("nhanvien").select("*").eq("email", email).execute()
    return res.data[0] if res.data else None



def get_customer_by_id(customer_id):
    return supabase.table("khachhang").select("*").eq("makhachhang", customer_id).single().execute()

def get_user_by_credentials(phone, cccd):
    return supabase.table("khachhang").select("*") \
        .eq("sodienthoai", phone) \
        .eq("cccd", cccd).single().execute()

def get_available_rooms():
    try:
        response = supabase.table("phong").select("*").eq("trangthai", "Trống").execute()
        return response.data
    except Exception as e:
        print(f"Lỗi khi lấy danh sách phòng: {e}")
        return []


def get_booking_amount(booking_id):
    try:
        response = supabase.table("datphong").select("tongtien").eq("madatphong", booking_id).single().execute()
        print("Kết quả truy vấn Supabase:", response)

        if response.data and "tongtien" in response.data:
            tongtien = response.data["tongtien"]
            if tongtien is None:
                print(f"[CẢNH BÁO] 'tongtien' của booking_id {booking_id} là NULL. Trả về 0.0")
                return 0.0
            return float(tongtien)
        else:
            raise ValueError(f"Không tìm thấy booking với ID: {booking_id}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Lỗi khi truy vấn Supabase:", e)
        raise
#mângermânger
def get_total_employees():
    return supabase.table("nhanvien").select("id").execute()

def get_total_bookings():
    return supabase.table("datphong").select("id").execute()

def get_total_revenue():
    res = supabase.table("hoadon").select("tongtien").eq("trangthai", "đã thanh toán").execute()
    return sum([float(item["tongtien"]) for item in res.data if item["tongtien"]])
# Thêm nhân viên mới
def insert_employee(data):
    return supabase.table("nhanvien").insert(data).execute()

# Cập nhật thông tin nhân viên
def update_employee(ma_nv, data):
    return supabase.table("nhanvien").update(data).eq("manv", ma_nv).execute()

# Lấy tổng số nhân viên
def get_total_employees():
    return supabase.table("nhanvien").select("*").execute()

# Lấy tổng số lượt đặt phòng
def get_total_bookings():
    return supabase.table("datphong").select("*").execute()

# Tính tổng doanh thu từ hóa đơn đã thanh toán
def get_total_revenue():
    res = supabase.table("hoadon").select("tongtien").eq("trangthai", "đã thanh toán").execute()
    if not res.data:
        return 0.0
    return sum(hoa_don.get("tongtien", 0) for hoa_don in res.data)

#dịch vụ
def get_all_services():
    return supabase.table("dichvu").select("*").execute()



# (Tùy chọn) Hàm hiển thị danh sách phòng trống dưới dạng HTML
def hien_thi_danh_sach_phong_trong_html():
    try:
        response = supabase.table("phong").select("*").eq("trangthai", "Trống").execute()
        danh_sach_phong = response.data

        if not danh_sach_phong:
            return "<p>⚠️ Không có phòng trống nào.</p>"

        html = """
        <table border="1" cellpadding="8" cellspacing="0">
            <thead>
                <tr>
                    <th>Mã phòng</th>
                    <th>Loại phòng</th>
                    <th>Giá (VNĐ)</th>
                    <th>Trạng thái</th>
                </tr>
            </thead>
            <tbody>
        """

        for phong in danh_sach_phong:
            ma_phong = phong.get("maphong", "N/A")
            loai_phong = phong.get("loaiphong", "Không rõ")
            gia = "{:,.0f}₫".format(phong.get("giaphong", 0))
            trang_thai = phong.get("trangthai", "Không rõ")
            html += f"""
                <tr>
                    <td>{ma_phong}</td>
                    <td>{loai_phong}</td>
                    <td>{gia}</td>
                    <td>{trang_thai}</td>
                </tr>
            """
        html += "</tbody></table>"
        return html

    except Exception as e:
        return f"<p>❌ Lỗi khi lấy danh sách phòng trống: {str(e)}</p>"
def get_booking_counts_by_room():
    response = supabase.table('datphong').select('maphong', count='*').execute()
    return {item['maphong']: item['count'] for item in response.data}