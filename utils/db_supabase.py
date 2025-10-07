# utils/db_supabase.py
import os
import sys
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import date, datetime
from typing import Dict, List, Optional

import bcrypt
from supabase import create_client, Client
from config import Config

# =========================
# Logging an toàn serverless
# =========================
logger = logging.getLogger("db_supabase")
if not logger.handlers:  # tránh nhân đôi handler khi Lambda warm start
    logger.setLevel(logging.INFO)
    if os.path.isdir("/tmp"):
        log_path = os.path.join("/tmp", "db_supabase.log")
        handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=2)
    else:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# =========================
# Supabase client
# =========================
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)

# =========================
# Hằng số/Enum
# =========================
VALID_ROLES = {'manager', 'letan', 'ketoan', 'donphong'}

VALID_DATPHONG_STATUSES = {
    "Chưa thanh toán", "Chờ xác nhận", "Đã xác nhận",
    "Đã thanh toán", "Đã check-in", "Đã hủy", "Đã trả phòng"
}

# Map hiển thị (VN) -> ENUM DB
PHONG_STATUS_MAPPING = {
    "Trống": "trong",
    "Đang sử dụng": "dang_su_dung",
    "Bảo trì": "bao_tri",
    "Đã đặt": "da_dat"
}
# Tập enum hợp lệ để ghi DB
PHONG_STATUS_ENUMS = set(PHONG_STATUS_MAPPING.values())

VALID_SERVICE_STATUS = {"Chưa xử lý", "Đang xử lý", "Đã hoàn thành"}
VALID_SERVICE_PAYMENT_STATUS = {"Chưa thanh toán", "Đã thanh toán"}

# =========================
# Helpers
# =========================
def _iso_to_date(v) -> date:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    raise ValueError("Ngày không đúng định dạng ISO (YYYY-MM-DD).")

def _normalize_room_status_for_db(value: str) -> str:
    """
    Chấp nhận cả nhãn tiếng Việt lẫn enum; trả về enum hợp lệ để ghi DB.
    """
    if value in PHONG_STATUS_ENUMS:
        return value
    if value in PHONG_STATUS_MAPPING:
        return PHONG_STATUS_MAPPING[value]
    raise ValueError(
        f"Trạng thái phòng không hợp lệ: {value}. "
        f"Hợp lệ (VN): {list(PHONG_STATUS_MAPPING.keys())} "
        f"hoặc enum: {list(PHONG_STATUS_ENUMS)}"
    )

# =========================
# Booking logic
# =========================
def get_booking_by_room_date(maphong: str, ngaynhanphong: str, ngaytraphong: str) -> Optional[Dict]:
    """Kiểm tra overlap đặt phòng (cho phép đặt nối tiếp)."""
    try:
        if not maphong or not ngaynhanphong or not ngaytraphong:
            raise ValueError("Mã phòng, ngày nhận phòng hoặc ngày trả phòng không được để trống.")

        response = (
            supabase.table('datphong')
            .select('*')
            .eq('maphong', maphong)
            .in_('trangthai', ['Chờ xác nhận', 'Đã xác nhận', 'Đã thanh toán', 'Đã check-in'])
            .execute()
        )

        for booking in response.data or []:
            ngaynhan_cu = booking['ngaynhanphong']
            ngaytra_cu = booking['ngaytraphong']
            # Overlap nếu: (new_start < old_end) and (new_end > old_start)
            if not (ngaytraphong <= ngaynhan_cu or ngaynhanphong >= ngaytra_cu):
                return booking
        return None
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra đặt phòng cho maphong={maphong}: {str(e)}")
        raise

def insert_user(data: Dict) -> Dict:
    """Thêm khách hàng mới vào bảng khachhang."""
    required_fields = ["hoten", "sodienthoai", "email", "cccd", "quoctich", "gioitinh", "ngaysinh", "diachi"]
    for field in required_fields:
        if not data.get(field):
            raise ValueError(f"Trường {field} không được để trống.")
    if not re.match(r"^\d{10}$", data.get("sodienthoai", "")):
        raise ValueError("Số điện thoại không hợp lệ (phải có 10 chữ số).")
    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", data.get("email", "")):
        raise ValueError("Email không hợp lệ.")
    if not re.match(r"^\d{12}$", data.get("cccd", "")):
        raise ValueError("CCCD không hợp lệ (phải có 12 chữ số).")

    try:
        response = supabase.table("khachhang").insert(data).execute()
        if not response.data or 'makhachhang' not in response.data[0]:
            logger.error(f"Không thể lấy makhachhang sau khi chèn: {response.data}")
            raise ValueError("Không thể lấy mã khách hàng sau khi đăng ký.")
        logger.info(f"Thêm khách hàng thành công: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi thêm khách hàng: {str(e)} - Dữ liệu: {data}")
        raise

def get_user_by_phone(phone: str) -> Optional[Dict]:
    """Lấy thông tin khách hàng theo số điện thoại."""
    if not phone or not re.match(r"^\d{10}$", phone):
        raise ValueError("Số điện thoại không hợp lệ (phải có 10 chữ số).")
    try:
        response = supabase.table("khachhang").select("*").eq("sodienthoai", phone).execute()
        if not response.data:
            logger.info(f"Không tìm thấy khách hàng với số điện thoại {phone}.")
            return None
        if len(response.data) > 1:
            logger.warning(f"Cảnh báo: Tìm thấy nhiều khách hàng với số điện thoại {phone}")
        logger.info(f"Lấy thông tin khách hàng với số điện thoại {phone}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi lấy khách hàng theo số điện thoại {phone}: {str(e)}")
        raise

def get_user_by_email(email: str) -> Optional[Dict]:
    """Lấy thông tin khách hàng theo email."""
    if not email or not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        raise ValueError("Email không hợp lệ.")
    try:
        response = supabase.table("khachhang").select("*").eq("email", email).execute()
        logger.info(f"Lấy thông tin khách hàng với email {email}: {response.data[0] if response.data else None}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Lỗi khi lấy khách hàng theo email {email}: {str(e)}")
        raise

def get_customer_by_id(customer_id: str) -> Optional[Dict]:
    """Lấy thông tin khách hàng theo mã khách hàng."""
    if not customer_id:
        raise ValueError("Mã khách hàng không hợp lệ.")
    try:
        response = supabase.table("khachhang").select("*").eq("makhachhang", customer_id).execute()
        logger.info(f"Lấy thông tin khách hàng với makhachhang={customer_id}: {response.data[0] if response.data else None}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Lỗi khi lấy khách hàng {customer_id}: {str(e)}")
        raise

def get_user_by_credentials(phone: str, cccd: str) -> Optional[Dict]:
    """Xác thực khách hàng bằng số điện thoại và CCCD."""
    if not phone or not re.match(r"^\d{10}$", phone):
        raise ValueError("Số điện thoại không hợp lệ (phải có 10 chữ số).")
    if not cccd or not re.match(r"^\d{12}$", cccd):
        raise ValueError("CCCD không hợp lệ (phải có 12 chữ số).")
    try:
        response = supabase.table("khachhang").select("*").eq("sodienthoai", phone).eq("cccd", cccd).execute()
        logger.info(f"Xác thực khách hàng với sodienthoai={phone}, cccd={cccd}: {response.data[0] if response.data else None}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Lỗi khi xác thực khách hàng: {str(e)}")
        raise

def insert_booking(data: Dict) -> Dict:
    """
    Thêm đơn đặt phòng mới vào bảng datphong.
    - Cho phép ngaynhanphong == ngaytraphong -> nights = 1
    - Tính tongtien = giaphong * nights (chưa gồm dịch vụ)
    - Kiểm tra trùng lịch
    """
    required_fields = ["makhachhang", "maphong", "ngaynhanphong", "ngaytraphong"]
    for field in required_fields:
        if not data.get(field):
            raise ValueError(f"Trường {field} không được để trống.")

    if "trangthai" not in data:
        data["trangthai"] = "Chờ xác nhận"
    if data.get("trangthai") not in VALID_DATPHONG_STATUSES:
        raise ValueError(f"Trạng thái đặt phòng không hợp lệ: {data.get('trangthai')}.")

    if data.get("songuoi") is not None:
        try:
            if not isinstance(data["songuoi"], int):
                data["songuoi"] = int(data["songuoi"])
        except Exception:
            raise ValueError("Số người phải là số nguyên.")
        if data["songuoi"] <= 0:
            raise ValueError("Số người phải lớn hơn 0.")

    if data.get("sokhachdicung") is not None and not isinstance(data["sokhachdicung"], str):
        data["sokhachdicung"] = str(data["sokhachdicung"])

    if not data.get("thoigiancheckindukien"):
        data["thoigiancheckindukien"] = None
    else:
        try:
            datetime.fromisoformat(data["thoigiancheckindukien"].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Giá trị thoigiancheckindukien không hợp lệ: {data['thoigiancheckindukien']}")

    try:
        maphong = data["maphong"]

        ngaynhanphong = _iso_to_date(data["ngaynhanphong"])
        ngaytraphong = _iso_to_date(data["ngaytraphong"])

        today = datetime.now().date()
        if ngaynhanphong < today:
            raise ValueError("Ngày nhận phòng không được trước ngày hiện tại.")
        if ngaytraphong < ngaynhanphong:
            raise ValueError("Ngày trả phòng phải sau hoặc bằng ngày nhận phòng.")

        nights = (ngaytraphong - ngaynhanphong).days or 1

        existing_booking = get_booking_by_room_date(maphong, ngaynhanphong.isoformat(), ngaytraphong.isoformat())
        if existing_booking:
            raise ValueError(f"Phòng {maphong} đã được đặt từ {existing_booking['ngaynhanphong']} đến {existing_booking['ngaytraphong']}.")

        room_resp = supabase.table("phong").select("giaphong").eq("maphong", maphong).execute()
        room_list = getattr(room_resp, "data", None)
        if not room_list:
            raise ValueError(f"Phòng {maphong} không tồn tại.")
        raw_price = room_list[0].get("giaphong")
        try:
            room_price = float(raw_price)
        except Exception:
            raise ValueError(f"Giá phòng của phòng {maphong} không hợp lệ: {raw_price}")

        makhachhang = data["makhachhang"]
        if not get_customer_by_id(str(makhachhang)):
            required_new_customer = ["hoten", "cccd", "sodienthoai", "quoctich", "gioitinh", "ngaysinh", "diachi"]
            if all(k in data and data[k] for k in required_new_customer):
                new_customer = insert_user({
                    "hoten": data["hoten"],
                    "cccd": data["cccd"],
                    "sodienthoai": data["sodienthoai"],
                    "email": data.get("email", ""),
                    "quoctich": data["quoctich"],
                    "gioitinh": data["gioitinh"],
                    "ngaysinh": data["ngaysinh"],
                    "diachi": data["diachi"]
                })
                makhachhang = new_customer.get("makhachhang", makhachhang)
                data["makhachhang"] = makhachhang
            else:
                raise ValueError("Không tìm thấy khách hàng và thiếu thông tin để tạo mới.")

        data["tongtien"] = room_price * nights
        data["ngaynhanphong"] = ngaynhanphong.isoformat()
        data["ngaytraphong"] = ngaytraphong.isoformat()

        response = supabase.table("datphong").insert(data).execute()
        resp_data = getattr(response, "data", None)
        if resp_data and len(resp_data) > 0:
            # Cập nhật trạng thái phòng -> 'đang sử dụng' (enum)
            try:
                supabase.table("phong").update({"trangthai": PHONG_STATUS_MAPPING["Đang sử dụng"]}).eq("maphong", maphong).execute()
            except Exception as ex_upd:
                logger.warning(f"Không thể cập nhật trạng thái phòng {maphong}: {ex_upd}")
            return resp_data[0]

        raise ValueError("Không thể tạo đơn đặt phòng (DB trả về rỗng).")
    except Exception as e:
        logger.error(f"Lỗi khi tạo đơn đặt phòng: {str(e)} - Dữ liệu: {data}", exc_info=True)
        raise ValueError(f"Lỗi khi tạo đơn đặt phòng: {str(e)}")

def update_booking_payment(madatphong: str, magiaodichpaypal: str) -> Dict:
    """Cập nhật mã giao dịch PayPal và trạng thái thanh toán cho đặt phòng."""
    if not madatphong or not magiaodichpaypal:
        raise ValueError("Mã đặt phòng hoặc mã giao dịch PayPal không hợp lệ.")
    try:
        response = supabase.table("datphong").update({
            "magiaodichpaypal": magiaodichpaypal,
            "trangthai": "Đã thanh toán"
        }).eq("madatphong", madatphong).execute()
        if not response.data:
            raise ValueError(f"Không tìm thấy đặt phòng với madatphong {madatphong}")
        logger.info(f"Cập nhật mã giao dịch PayPal cho madatphong {madatphong}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật mã giao dịch PayPal cho madatphong {madatphong}: {str(e)}")
        raise

def get_available_rooms(checkin_date: str = None, checkout_date: str = None) -> List[Dict]:
    """Lấy danh sách phòng trống, loại trừ các phòng bị trùng lịch đặt (trạng thái hiển thị)."""
    try:
        all_rooms = supabase.table("phong").select(
            "maphong, loaiphong, giaphong, succhua, dientich, hinhanh"
        ).execute().data or []

        if not all_rooms:
            logger.info("Không có phòng nào hợp lệ")
            return []

        if not (checkin_date and checkout_date):
            for room in all_rooms:
                room['trangthai'] = "Trống"
                room['thongtin_dat'] = None
            return all_rooms

        booked_rooms = (
            supabase.table("datphong")
            .select("maphong, ngaynhanphong, ngaytraphong")
            .in_("trangthai", ["Đã xác nhận", "Đã thanh toán", "Đã check-in"])
            .execute()
            .data or []
        )

        room_status = {room['maphong']: {"trangthai": "Trống", "thongtin_dat": None} for room in all_rooms}

        for booking in booked_rooms:
            booking_checkin = booking["ngaynhanphong"]
            booking_checkout = booking["ngaytraphong"]
            if booking_checkin < checkout_date and booking_checkout > checkin_date:
                room_status[booking["maphong"]] = {
                    "trangthai": "Đã đặt",
                    "thongtin_dat": f"Đã đặt từ {booking_checkin} đến {booking_checkout}"
                }

        available_rooms = []
        for room in all_rooms:
            room['trangthai'] = room_status[room['maphong']]['trangthai']
            room['thongtin_dat'] = room_status[room['maphong']]['thongtin_dat']
            if room['trangthai'] == "Trống":
                available_rooms.append(room)

        logger.info(f"Lấy được {len(available_rooms)} phòng trống cho {checkin_date} đến {checkout_date}")
        return available_rooms
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn phòng trống: {str(e)}", exc_info=True)
        return []

def get_room_by_id(ma_phong: str) -> Optional[Dict]:
    """Lấy thông tin phòng theo mã phòng."""
    if not ma_phong:
        raise ValueError("Mã phòng không hợp lệ.")
    try:
        response = (
            supabase.table("phong")
            .select("maphong, loaiphong, giaphong, succhua, trangthai, dientich, hinhanh")
            .eq("maphong", ma_phong)
            .gt("giaphong", 0)
            .execute()
        )
        if response.data:
            logger.info(f"Lấy thông tin phòng {ma_phong}: {response.data[0]}")
            return response.data[0]
        logger.info(f"Không tìm thấy phòng {ma_phong} với giaphong > 0")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi lấy phòng {ma_phong}: {str(e)}")
        raise

def get_rooms() -> List[Dict]:
    """Lấy danh sách tất cả các phòng (quản lý, không lọc theo đặt)."""
    try:
        response = supabase.table("phong").select(
            "maphong, loaiphong, giaphong, succhua, trangthai, dientich, hinhanh"
        ).gt("giaphong", 0).execute()
        logger.info(f"Lấy được {len(response.data or [])} phòng hợp lệ")
        return response.data or []
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách phòng: {str(e)}")
        return []

def get_invoices_by_customer_id(customer_id: str) -> List[Dict]:
    """Lấy danh sách hóa đơn của khách hàng theo mã khách hàng."""
    if not customer_id:
        raise ValueError("Mã khách hàng không hợp lệ.")
    try:
        response = (
            supabase.table("hoadon")
            .select("*, datphong(maphong, ngaynhanphong, ngaytraphong)")
            .eq("makhachhang", customer_id)
            .gt("tongtien", 0)
            .execute()
        )
        logger.info(f"Lấy được {len(response.data or [])} hóa đơn cho makhachhang={customer_id}")
        return response.data or []
    except Exception as e:
        logger.error(f"Lỗi khi lấy hóa đơn của khách hàng {customer_id}: {str(e)}")
        return []

def create_invoice(madatphong: str, makhachhang: str, tongtien: float, phuongthucthanhtoan: str,
                   ngaylap: str = None, magiaodichpaypal: str = None) -> Dict:
    """Tạo hóa đơn mới (chỉ khi đặt phòng đã thanh toán)."""
    madatphong = str(madatphong)
    if not madatphong:
        raise ValueError("Mã đặt phòng không hợp lệ.")
    if not makhachhang:
        raise ValueError("Mã khách hàng không hợp lệ.")
    if tongtien is None or tongtien <= 0:
        raise ValueError(f"Tổng tiền không hợp lệ: {tongtien}.")
    if not phuongthucthanhtoan:
        raise ValueError("Phương thức thanh toán không hợp lệ.")
    try:
        booking = supabase.table("datphong").select("trangthai, tongtien").eq("madatphong", madatphong).execute().data
        if not booking:
            raise ValueError(f"Không tìm thấy đặt phòng với madatphong {madatphong}")
        if booking[0]["trangthai"] != "Đã thanh toán":
            raise ValueError(f"Đặt phòng {madatphong} chưa được thanh toán (hiện: {booking[0]['trangthai']}).")
        if float(booking[0]["tongtien"]) <= 0:
            raise ValueError(f"Tổng tiền của đặt phòng {madatphong} không hợp lệ: {booking[0]['tongtien']}")

        services = supabase.table("chitietdichvu").select("trangthai, thanhtien").eq("madatphong", madatphong).execute().data or []
        total_service_cost = sum(float(s["thanhtien"]) for s in services if s["trangthai"] == "Đã thanh toán")

        existing_invoice = supabase.table("hoadon").select("mahoadon").eq("madatphong", madatphong).execute().data
        if existing_invoice:
            raise ValueError(f"Hóa đơn cho madatphong {madatphong} đã tồn tại.")

        invoice = {
            "madatphong": int(madatphong),
            "makhachhang": int(makhachhang),
            "tongtien": float(tongtien) + total_service_cost,
            "phuongthucthanhtoan": phuongthucthanhtoan,
            "ngaylap": ngaylap if ngaylap else datetime.now().strftime('%Y-%m-%d'),
            "tongtien_dichvu": total_service_cost,
            "magiaodichpaypal": magiaodichpaypal
        }
        response = supabase.table("hoadon").insert(invoice).execute()
        if response.data:
            logger.info(f"Hóa đơn được tạo: {response.data[0]}")
            return response.data[0]
        raise ValueError("Không thể tạo hóa đơn.")
    except Exception as e:
        logger.error(f"Lỗi khi tạo hóa đơn cho madatphong {madatphong}: {str(e)}")
        raise

def update_invoice_with_service(madatphong: str, thanhtien_dichvu: float) -> Dict:
    """Cập nhật hóa đơn với thành tiền dịch vụ."""
    madatphong = str(madatphong)
    if not madatphong:
        raise ValueError("Mã đặt phòng không hợp lệ.")
    if thanhtien_dichvu is None or thanhtien_dichvu < 0:
        raise ValueError("Thành tiền dịch vụ không hợp lệ.")
    try:
        invoice = supabase.table("hoadon").select("mahoadon, tongtien, tongtien_dichvu").eq("madatphong", madatphong).execute().data
        if not invoice:
            raise ValueError(f"Không tìm thấy hóa đơn cho madatphong {madatphong}")
        invoice = invoice[0]
        if float(invoice["tongtien"]) <= 0:
            raise ValueError(f"Tổng tiền của hóa đơn {madatphong} không hợp lệ: {invoice['tongtien']}")
        new_tongtien_dichvu = float(invoice.get("tongtien_dichvu", 0.0)) + float(thanhtien_dichvu)
        new_tongtien = float(invoice["tongtien"]) + float(thanhtien_dichvu)
        response = supabase.table("hoadon").update({
            "tongtien": new_tongtien,
            "tongtien_dichvu": new_tongtien_dichvu
        }).eq("mahoadon", invoice["mahoadon"]).execute()
        if not response.data:
            raise ValueError(f"Không thể cập nhật hóa đơn cho madatphong {madatphong}")
        logger.info(f"Cập nhật hóa đơn với dịch vụ cho madatphong {madatphong}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật hóa đơn cho madatphong {madatphong}: {str(e)}")
        raise

def confirm_payment(mahoadon: str) -> Dict:
    """Xác nhận thanh toán cho hóa đơn, cập nhật trạng thái đặt phòng."""
    if not mahoadon:
        raise ValueError("Mã hóa đơn không hợp lệ.")
    try:
        invoice = supabase.table("hoadon").select("madatphong, tongtien").eq("mahoadon", mahoadon).execute().data
        if not invoice:
            raise ValueError(f"Không tìm thấy hóa đơn với mahoadon {mahoadon}")
        if float(invoice[0]["tongtien"]) <= 0:
            raise ValueError(f"Tổng tiền của hóa đơn {mahoadon} không hợp lệ: {invoice[0]['tongtien']}")

        madatphong = invoice[0]["madatphong"]
        response = supabase.table("datphong").update({
            "trangthai": "Đã thanh toán"
        }).eq("madatphong", madatphong).execute()
        if not response.data:
            raise ValueError(f"Không tìm thấy đặt phòng với madatphong {madatphong}")
        logger.info(f"Xác nhận thanh toán cho mahoadon {mahoadon}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi xác nhận thanh toán cho mahoadon {mahoadon}: {str(e)}")
        raise

def get_unpaid_bookings_and_services() -> Dict:
    """Lấy danh sách đặt phòng và dịch vụ chưa thanh toán."""
    try:
        unpaid_bookings = (
            supabase.table("datphong")
            .select("madatphong, maphong, makhachhang, tongtien, trangthai, khachhang(hoten)")
            .neq("trangthai", "Đã thanh toán")
            .execute().data or []
        )
        unpaid_services = (
            supabase.table("chitietdichvu")
            .select("machitiet, madatphong, madichvu, soluong, thanhtien, trangthai, datphong(maphong), dichvu(tendichvu)")
            .neq("trangthai", "Đã thanh toán")
            .execute().data or []
        )
        logger.info(f"Lấy được {len(unpaid_bookings)} đặt phòng và {len(unpaid_services)} dịch vụ chưa thanh toán")
        return {"unpaid_bookings": unpaid_bookings, "unpaid_services": unpaid_services}
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách chưa thanh toán: {str(e)}")
        return {"unpaid_bookings": [], "unpaid_services": []}

def get_invoice_by_booking_id(madatphong: str) -> Optional[Dict]:
    """Lấy hóa đơn theo mã đặt phòng."""
    madatphong = str(madatphong)
    if not madatphong:
        raise ValueError("Mã đặt phòng không hợp lệ.")
    try:
        response = supabase.table("hoadon").select("*").eq("madatphong", madatphong).gt("tongtien", 0).execute()
        logger.info(f"Lấy hóa đơn cho madatphong {madatphong}: {response.data[0] if response.data else None}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Lỗi khi lấy hóa đơn cho madatphong {madatphong}: {str(e)}")
        raise

def get_service_by_id(madichvu: str) -> Optional[Dict]:
    """Lấy thông tin dịch vụ theo mã dịch vụ."""
    if not madichvu:
        raise ValueError("Mã dịch vụ không hợp lệ.")
    try:
        response = supabase.table("dichvu").select("*").eq("madichvu", madichvu).execute()
        logger.info(f"Lấy thông tin dịch vụ {madichvu}: {response.data[0] if response.data else None}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Lỗi khi lấy dịch vụ {madichvu}: {str(e)}")
        raise

def get_all_services():
    """Lấy toàn bộ dịch vụ, chuẩn hoá giá và trường trống."""
    try:
        response = supabase.table('dichvu').select('*').execute()
        if hasattr(response, 'data') and response.data:
            services = response.data
            for service in services:
                try:
                    service['giadichvu'] = float(service.get('giadichvu', 0))
                    if service['giadichvu'] < 0:
                        logger.warning(f"Dịch vụ {service.get('madichvu')} có giá âm: {service['giadichvu']}")
                        service['giadichvu'] = 0
                except (TypeError, ValueError):
                    logger.error(f"Dịch vụ {service.get('madichvu')} có giá không hợp lệ: {service.get('giadichvu')}")
                    service['giadichvu'] = 0
                service['tendichvu'] = service.get('tendichvu', 'Không có tên')
                service['mota'] = service.get('mota', '')
                service['hinhanh'] = service.get('hinhanh') or None
            logger.info(f"Danh sách dịch vụ từ Supabase: {services}")
            return services
        else:
            logger.error("Không lấy được danh sách dịch vụ từ Supabase.")
            return []
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách dịch vụ: {str(e)}")
        return []

def insert_service_usage(data: Dict) -> Dict:
    """Thêm chi tiết sử dụng dịch vụ."""
    try:
        required_fields = ['madatphong', 'madichvu', 'soluong', 'thanhtien', 'trangthai', 'trangthaithanhtoan']
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValueError(f"Thiếu trường bắt buộc: {field}")

        if data.get("trangthai") not in VALID_SERVICE_STATUS:
            raise ValueError(f"Trạng thái dịch vụ không hợp lệ: {data.get('trangthai')}. Phải thuộc {VALID_SERVICE_STATUS}")
        if data.get("trangthaithanhtoan") not in VALID_SERVICE_PAYMENT_STATUS:
            raise ValueError(f"Trạng thái thanh toán không hợp lệ: {data.get('trangthaithanhtoan')}")

        insert_data = {
            'madatphong': data['madatphong'],
            'madichvu': data['madichvu'],
            'soluong': data['soluong'],
            'thanhtien': data['thanhtien'],
            'trangthai': data['trangthai'],
            'trangthaithanhtoan': data['trangthaithanhtoan'],
            'magiaodich': data.get('magiaodich'),
            'ngaydat': data.get('ngaydat', datetime.now().isoformat())
        }
        response = supabase.table("chitietdichvu").insert(insert_data).execute()
        logger.info(f"Inserted service usage: {response.data}")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Lỗi khi thêm chi tiết dịch vụ: {str(e)}\nDữ liệu: {data}")
        raise

def get_admin_by_email(email: str) -> Optional[Dict]:
    """Lấy thông tin nhân viên theo email."""
    if not email or not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        raise ValueError("Email không hợp lệ.")
    try:
        response = supabase.table("nhanvien").select("*").eq("email", email).execute()
        logger.info(f"Lấy thông tin nhân viên với email {email}: {response.data[0] if response.data else None}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Lỗi khi lấy nhân viên theo email {email}: {str(e)}")
        raise

def insert_employee(data: Dict) -> Dict:
    """Thêm nhân viên mới vào bảng nhanvien."""
    required_fields = ["hoten", "email", "sodienthoai", "matkhau", "chucvu"]
    for field in required_fields:
        if not data.get(field):
            raise ValueError(f"Trường {field} không được để trống.")
    if "email" in data and not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", data["email"]):
        raise ValueError("Email không hợp lệ.")
    if "sodienthoai" in data and not re.match(r"^\d{10}$", data["sodienthoai"]):
        raise ValueError("Số điện thoại không hợp lệ (phải có 10 số).")
    if data.get("chucvu") not in VALID_ROLES:
        raise ValueError(f"Chức vụ không hợp lệ: {data['chucvu']}. Chức vụ phải thuộc {VALID_ROLES}")

    try:
        data = data.copy()
        data["matkhau"] = bcrypt.hashpw(data["matkhau"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        response = supabase.table("nhanvien").insert(data).execute()
        if not response.data:
            raise ValueError("Không thể thêm nhân viên.")
        logger.info(f"Thêm nhân viên thành công: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi thêm nhân viên: {str(e)}")
        raise

def update_employee(ma_nhan_vien: str, data: Dict) -> Dict:
    """Cập nhật thông tin nhân viên."""
    if not ma_nhan_vien:
        raise ValueError("Mã nhân viên không hợp lệ.")
    if "email" in data and not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", data["email"]):
        raise ValueError("Email không hợp lệ.")
    if "sodienthoai" in data and not re.match(r"^\d{10}$", data["sodienthoai"]):
        raise ValueError("Số điện thoại không hợp lệ (phải có 10 chữ số).")
    if "chucvu" in data and data["chucvu"] not in VALID_ROLES:
        raise ValueError(f"Chức vụ không hợp lệ: {data['chucvu']}. Chức vụ phải thuộc {VALID_ROLES}")

    try:
        data = data.copy()
        if "matkhau" in data and data["matkhau"]:
            data["matkhau"] = bcrypt.hashpw(data["matkhau"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        response = supabase.table("nhanvien").update(data).eq("manhanvien", ma_nhan_vien).execute()
        if not response.data:
            raise ValueError(f"Không tìm thấy nhân viên với mã: {ma_nhan_vien}")
        logger.info(f"Cập nhật nhân viên {ma_nhan_vien}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật nhân viên {ma_nhan_vien}: {str(e)}")
        raise

def get_all_employees() -> List[Dict]:
    """Lấy danh sách tất cả nhân viên."""
    try:
        response = supabase.table("nhanvien").select("*").execute()
        logger.info(f"Lấy được {len(response.data or [])} nhân viên")
        return response.data or []
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách nhân viên: {str(e)}")
        return []

def update_room_status(ma_phong: str, trang_thai_vn: str) -> Dict:
    """Cập nhật trạng thái phòng bằng nhãn tiếng Việt -> enum."""
    if not ma_phong:
        raise ValueError("Mã phòng không hợp lệ.")
    if trang_thai_vn not in PHONG_STATUS_MAPPING:
        raise ValueError(f"Trạng thái không hợp lệ: {trang_thai_vn}. Phải thuộc {list(PHONG_STATUS_MAPPING.keys())}")
    try:
        trangthai_enum = PHONG_STATUS_MAPPING[trang_thai_vn]
        response = supabase.table("phong").update({"trangthai": trangthai_enum}).eq("maphong", ma_phong).execute()
        if not response.data:
            raise ValueError(f"Không tìm thấy phòng với mã: {ma_phong}")
        return response.data[0]
    except Exception as e:
        raise ValueError(f"Lỗi khi cập nhật trạng thái phòng {ma_phong}: {str(e)}")

def update_room(ma_phong: str, data: Dict) -> Dict:
    """Cập nhật thông tin phòng (validate đúng enum trạng thái)."""
    if not ma_phong:
        raise ValueError("Mã phòng không hợp lệ.")
    if data.get("loaiphong") is not None and not data["loaiphong"]:
        raise ValueError("Loại phòng không được để trống.")
    if data.get("giaphong") is not None and float(data["giaphong"]) <= 0:
        raise ValueError("Giá phòng phải lớn hơn 0.")
    if data.get("succhua") is not None and int(data["succhua"]) <= 0:
        raise ValueError("Sức chứa phải lớn hơn 0.")
    if data.get("dientich") is not None and float(data["dientich"]) <= 0:
        raise ValueError("Diện tích phải lớn hơn 0.")

    payload = data.copy()
    if "trangthai" in payload and payload["trangthai"]:
        # chấp nhận cả vn/enum, lưu xuống enum
        payload["trangthai"] = _normalize_room_status_for_db(payload["trangthai"])

    try:
        response = supabase.table("phong").update(payload).eq("maphong", ma_phong).execute()
        if not response.data:
            raise ValueError(f"Không tìm thấy phòng với mã: {ma_phong}")
        logger.info(f"Cập nhật phòng {ma_phong}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật phòng {ma_phong}: {str(e)}")
        raise

def get_total_employees() -> int:
    """Tính tổng số nhân viên."""
    try:
        response = supabase.table("nhanvien").select("manhanvien", count="exact").execute()
        count = response.count if getattr(response, "count", None) is not None else 0
        logger.info(f"Tổng số nhân viên: {count}")
        return count
    except Exception as e:
        logger.error(f"Lỗi khi lấy tổng số nhân viên: {str(e)}")
        return 0

def get_total_bookings() -> int:
    """Tính tổng số lượt đặt phòng."""
    try:
        response = supabase.table("datphong").select("madatphong", count="exact").execute()
        count = response.count if getattr(response, "count", None) is not None else 0
        logger.info(f"Tổng số lượt đặt phòng: {count}")
        return count
    except Exception as e:
        logger.error(f"Lỗi khi lấy tổng số lượt đặt phòng: {str(e)}")
        return 0

def get_total_revenue() -> float:
    """Tính tổng doanh thu từ hóa đơn."""
    try:
        response = supabase.table("hoadon").select("tongtien").gt("tongtien", 0).execute()
        total = sum(float(t.get("tongtien", 0)) for t in (response.data or []))
        logger.info(f"Tổng doanh thu: {total}")
        return total
    except Exception as e:
        logger.error(f"Lỗi khi tính tổng doanh thu: {str(e)}")
        return 0.0

def update_payment_status(ma_hoa_don: str, transaction_id: str) -> Dict:
    """Cập nhật trạng thái thanh toán và mã giao dịch PayPal cho đặt phòng."""
    if not ma_hoa_don:
        raise ValueError("Mã hóa đơn không hợp lệ.")
    if not transaction_id:
        raise ValueError("Mã giao dịch PayPal không hợp lệ.")
    try:
        invoice = supabase.table("hoadon").select("madatphong, tongtien").eq("mahoadon", ma_hoa_don).execute().data
        if not invoice:
            raise ValueError(f"Không tìm thấy hóa đơn với mahoadon {ma_hoa_don}")
        if float(invoice[0]["tongtien"]) <= 0:
            raise ValueError(f"Tổng tiền của hóa đơn {ma_hoa_don} không hợp lệ: {invoice[0]['tongtien']}")

        madatphong = invoice[0]["madatphong"]
        response = supabase.table("datphong").update({
            "trangthai": "Đã thanh toán",
            "magiaodichpaypal": transaction_id
        }).eq("madatphong", madatphong).execute()
        if not response.data:
            raise ValueError(f"Không tìm thấy đặt phòng với madatphong {madatphong}")
        logger.info(f"Cập nhật trạng thái thanh toán cho mahoadon {ma_hoa_don}: {response.data[0]}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật trạng thái thanh toán {ma_hoa_don}: {str(e)}")
        raise

def get_booking_counts_by_room() -> Dict:
    """Thống kê số lượt đặt phòng theo mã phòng."""
    try:
        response = supabase.table("datphong").select("maphong").execute()
        booking_counts: Dict[str, int] = {}
        for item in response.data or []:
            maphong = item["maphong"]
            booking_counts[maphong] = booking_counts.get(maphong, 0) + 1
        logger.info(f"Thống kê số lượt đặt phòng: {booking_counts}")
        return booking_counts
    except Exception as e:
        logger.error(f"Lỗi khi lấy số lượt đặt phòng: {str(e)}")
        return {}

def delete_employee(ma_nhan_vien: str) -> Dict:
    """Xóa nhân viên theo mã nhân viên."""
    if not ma_nhan_vien:
        raise ValueError("Mã nhân viên không hợp lệ.")
    try:
        response = supabase.table("nhanvien").delete().eq("manhanvien", ma_nhan_vien).execute()
        logger.info(f"Xóa nhân viên {ma_nhan_vien}: {response.data[0] if response.data else {}}")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Lỗi khi xóa nhân viên {ma_nhan_vien}: {str(e)}")
        raise

def delete_room(ma_phong: str) -> Dict:
    """Xóa phòng nếu không có đặt phòng đang hoạt động."""
    if not ma_phong:
        raise ValueError("Mã phòng không hợp lệ.")
    try:
        bookings = (
            supabase.table("datphong").select("madatphong")
            .eq("maphong", ma_phong)
            .in_("trangthai", ["Đã xác nhận", "Đã thanh toán", "Đã check-in"])
            .execute().data
        )
        if bookings:
            raise ValueError(f"Phòng {ma_phong} đang được đặt, không thể xóa.")
        response = supabase.table("phong").delete().eq("maphong", ma_phong).execute()
        logger.info(f"Xóa phòng {ma_phong}: {response.data[0] if response.data else {}}")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Lỗi khi xóa phòng {ma_phong}: {str(e)}")
        raise

def delete_service(ma_dich_vu: str) -> Dict:
    """Xóa dịch vụ nếu không có chi tiết dịch vụ liên quan."""
    if not ma_dich_vu:
        raise ValueError("Mã dịch vụ không hợp lệ.")
    try:
        service_usages = supabase.table("chitietdichvu").select("machitiet").eq("madichvu", ma_dich_vu).execute().data
        if service_usages:
            raise ValueError(f"Dịch vụ {ma_dich_vu} đang được sử dụng, không thể xóa.")
        response = supabase.table("dichvu").delete().eq("madichvu", ma_dich_vu).execute()
        logger.info(f"Xóa dịch vụ {ma_dich_vu}: {response.data[0] if response.data else {}}")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Lỗi khi xóa dịch vụ {ma_dich_vu}: {str(e)}")
        raise

def auto_checkout_expired_bookings() -> int:
    """Tự động checkout các phòng đã quá hạn."""
    try:
        today = datetime.now().date().isoformat()
        expired_bookings = (
            supabase.table("datphong")
            .select("madatphong, maphong, trangthai, ngaytraphong")
            .lt("ngaytraphong", today)
            .neq("trangthai", "Đã trả phòng")
            .neq("trangthai", "Đã hủy")
            .execute()
            .data or []
        )
        if not expired_bookings:
            logger.info("Không có phòng nào cần auto checkout hôm nay.")
            return 0

        count = 0
        for booking in expired_bookings:
            madatphong = booking["madatphong"]
            maphong = booking["maphong"]

            # 1) cập nhật trạng thái đặt phòng
            supabase.table("datphong").update({"trangthai": "Đã trả phòng"}).eq("madatphong", madatphong).execute()
            # 2) cập nhật trạng thái phòng về enum 'trong'
            supabase.table("phong").update({"trangthai": PHONG_STATUS_MAPPING["Trống"]}).eq("maphong", maphong).execute()

            count += 1
            logger.info(f"Tự động checkout phòng {maphong} (đơn #{madatphong})")

        return count
    except Exception as e:
        logger.error(f"Lỗi khi tự động checkout: {str(e)}", exc_info=True)
        return 0
