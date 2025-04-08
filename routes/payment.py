from flask import Blueprint, flash, redirect, request, url_for
import paypalrestsdk
from config import Config
from utils.db_supabase import update_payment_status, get_booking_amount

payment_bp = Blueprint('payment', __name__)

paypalrestsdk.configure({
    "mode": Config.PAYPAL_MODE,
    "client_id": Config.PAYPAL_CLIENT_ID,
    "client_secret": Config.PAYPAL_CLIENT_SECRET
})

# Tạo thanh toán PayPal
@payment_bp.route('/<int:booking_id>')
def pay(booking_id):
    try:
        amount = get_booking_amount(booking_id)  # Lấy tổng tiền từ Supabase
        amount_str = f"{amount:.2f}"  # PayPal yêu cầu định dạng 2 chữ số thập phân

        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": amount_str,
                    "currency": "USD"
                },
                "description": f"Thanh toán đặt phòng mã {booking_id}",
                "custom": str(booking_id)
            }],
            "redirect_urls": {
                "return_url": "http://localhost:5000/payment/success",
                "cancel_url": "http://localhost:5000/payment/cancel"
            }
        })

        if payment.create():
            approval_url = next(link.href for link in payment.links if link.rel == "approval_url")
            return redirect(approval_url)
        else:
            return "Lỗi khi tạo thanh toán", 500

    except Exception:
        return "Lỗi hệ thống", 500

# Xử lý callback khi thanh toán thành công
@payment_bp.route('/success')
def success():
    try:
        payment_id = request.args.get('paymentId')
        payer_id = request.args.get('PayerID')

        if not payment_id or not payer_id:
            flash("Thanh toán thất bại hoặc thiếu thông tin.", "error")
            return redirect(url_for('index'))

        payment = paypalrestsdk.Payment.find(payment_id)

        if payment.execute({"payer_id": payer_id}):
            transaction_id = payment.transactions[0].related_resources[0].sale.id
            booking_id = int(payment.transactions[0].custom)

            update_payment_status(booking_id, transaction_id)
            flash("Thanh toán thành công! Cảm ơn bạn.", "success")
        else:
            flash("Lỗi khi hoàn tất thanh toán.", "error")

    except Exception:
        flash("Lỗi hệ thống khi xử lý thanh toán.", "error")

    return redirect(url_for('index'))

# Người dùng hủy thanh toán
@payment_bp.route('/cancel')
def cancel():
    flash("Bạn đã hủy giao dịch thanh toán.", "warning")
    return redirect(url_for('index'))
