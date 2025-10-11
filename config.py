import os
from supabase import create_client, Client

class Config:
    # Flask and JWT configurations
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "my-secure-jwt-key-2025!@#xai-grok3")
    SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey123")
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() == "true"

    # Supabase configurations
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://uaggzmqpvbtrinppmhrc.supabase.co")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVhZ2d6bXFwdmJ0cmlucHBtaHJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQwNzc0NjYsImV4cCI6MjA1OTY1MzQ2Nn0.Zc0ZUaYIi93E_xJ067M2c5gmY-WbHIG0epYvy3HureM")

    # Cloudinary configurations
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "dwczro6hp")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "648677879979597")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "-1D5fNq5hrtfGoIeZ8U7n8GHWi0")

    # PayPal configurations
    PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
    PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "AbypbYi579i233ITPW0LV76-LKvrvAHFpvTIPdrhdUNuLVMSdrDYhOvKpuOjs3IIIx-Aee1wU2bBl8r_")
    PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "EBkh8fIo65RfJU6x4BaNMrA8YNrerTAWvy8OxUTqW9wmQw6-Wsr_W4LIMysO8yGXyUYDC0b6Ui3ennT4")

    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "bui463241@gmail.com")  # Gmail dùng để gửi
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "svdmeghmbbhmjeuc")      # App Password Gmail
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
    SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey")


# Khởi tạo Supabase client
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)