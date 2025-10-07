# utils/enums.py
# mapping hiển thị (UI) -> giá trị lưu DB (enum)
MAP_TRANGTHAI_PHONG = {
    "Trống": "trong",
    "Đã sử dụng": "dang_su_dung",
    "Bảo trì": "dang_bao_tri"
}

# mapping ngược: DB -> hiển thị (nếu cần hiển thị ra UI)
MAP_TRANGTHAI_PHONG_REVERSE = {v: k for k, v in MAP_TRANGTHAI_PHONG.items()}
