from flask import Blueprint, flash, redirect, request, url_for, session, render_template
import paypalrestsdk
from datetime import datetime
from config import Config
from utils.db_supabase import supabase

payment_bp = Blueprint('payment', __name__)

paypalrestsdk.configure({
    "mode": Config.PAYPAL_MODE,
    "client_id": Config.PAYPAL_CLIENT_ID,
    "client_secret": Config.PAYPAL_CLIENT_SECRET
})

@payment_bp.route('/')
def pay():
    booking = session.get('datphong')
    if not booking:
        flash("Không có thông tin đặt phòng!", "error")
        return redirect(url_for('booking.dat_phong'))

    try:
        amount_str = f"{booking['tongtien']:.2f}"
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {"total": amount_str, "currency": "USD"},
                "description": "Thanh toán đặt phòng",
                "custom": "booking"
            }],
            "redirect_urls": {
                "return_url": url_for('payment.success', _external=True),
                "cancel_url": url_for('payment.cancel', _external=True)
            }
        })

        if payment.create():
            approval_url = next(link.href for link in payment.links if link.rel == "approval_url")
            return redirect(approval_url)
        else:
            flash("Lỗi khi tạo giao dịch thanh toán.", "error")
            return redirect(url_for('booking.dat_phong'))
    except Exception:
        flash("Lỗi hệ thống khi tạo giao dịch.", "error")
        return redirect(url_for('booking.dat_phong'))

@payment_bp.route('/success')
def success():
    try:
        payment_id = request.args.get('paymentId')
        payer_id = request.args.get('PayerID')

        if not payment_id or not payer_id:
            flash("Thiếu thông tin thanh toán!", "error")
            return redirect(url_for('index'))

        payment = paypalrestsdk.Payment.find(payment_id)
        if not payment.execute({"payer_id": payer_id}):
            flash("Lỗi khi hoàn tất thanh toán.", "error")
            return redirect(url_for('index'))

        booking = session.pop('datphong', None)
        if not booking:
            flash("Không tìm thấy thông tin đặt phòng!", "error")
            return redirect(url_for('index'))

        now = datetime.now()

        # 1. Lưu thông tin đặt phòng vào bảng datphong
        datphong_data = {
            'makhachhang': session['user']['id'],
            'maphong': booking['maphong'],
            'ngaydat': now.date().isoformat(),
            'ngaynhanphong': booking['ngaynhanphong'],
            'ngaytraphong': booking['ngaytraphong'],
            'songuoi': booking['songuoi'],
            'trangthai': 'Chờ xác nhận',
            'tongtien': booking['tongtien'],
            'yeucaudacbiet': booking['yeucaudacbiet'],
            'thoigiancheckindukien': booking['thoigiancheckindukien'],
            'sokhachdicung': booking['sokhachdicung'],
            'ghichudatphong': booking['ghichudatphong'],
            'thoigiandat': now.isoformat()
        }

        datphong_res = supabase.table('datphong').insert(datphong_data).execute()
        madatphong = datphong_res.data[0]['madatphong']

        # 2. Cập nhật trạng thái phòng
        supabase.table('phong').update({'trangthai': 'booked'}).eq('maphong', booking['maphong']).execute()

        # 3. Tạo hóa đơn
        hoadon_data = {
            'madatphong': madatphong,
            'makhachhang': session['user']['id'],
            'ngaylap': now.isoformat(),
            'tongtien': booking['tongtien'],
            'phuongthucthanhtoan': 'PayPal',
            'trangthai': 'đã thanh toán',
            'magiaodichpaypal': payment.id
        }
        supabase.table('hoadon').insert(hoadon_data).execute()

        flash("Thanh toán thành công! Đặt phòng của bạn đang chờ xác nhận.", "success")

        return render_template("payment_success.html", info={
            'ma_don': payment.id,
            'ten_nguoi_mua': payment.payer.payer_info.first_name + " " + payment.payer.payer_info.last_name,
            'email': payment.payer.payer_info.email,
            'so_tien': payment.transactions[0].amount.total,
            'don_vi_tien': payment.transactions[0].amount.currency
        })

    except Exception as e:
        print("❌ Lỗi hệ thống:", str(e))
        flash(f"Lỗi hệ thống: {str(e)}", "error")
        return redirect(url_for('index'))

@payment_bp.route('/cancel')
def cancel():
    flash("Bạn đã hủy giao dịch thanh toán.", "warning")
    return redirect(url_for('index'))

# (Tuỳ chọn) Thực hiện lại thanh toán thủ công nếu cần
@payment_bp.route('/execute')
def execute():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({'payer_id': payer_id}):
        datphong = session.get('datphong')
        if not datphong:
            return "Không tìm thấy dữ liệu đặt phòng trong session"

        supabase.table('datphong').insert(datphong).execute()
        supabase.table('phong').update({'trangthai': 'booked'}).eq('maphong', datphong['maphong']).execute()
        session.pop('datphong', None)

        return render_template("payment_success.html", info={
            'ma_don': payment.id,
            'ten_nguoi_mua': payment.payer.payer_info.first_name + " " + payment.payer.payer_info.last_name,
            'email': payment.payer.payer_info.email,
            'so_tien': payment.transactions[0].amount.total,
            'don_vi_tien': payment.transactions[0].amount.currency
        })

    return "Thanh toán thất bại!"
