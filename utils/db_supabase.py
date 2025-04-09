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

def get_user_by_email(email):
    res = supabase.table("khachhang").select("*").eq("email", email).single().execute()
    return res.data

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
