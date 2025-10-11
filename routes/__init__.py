import logging
from logging.handlers import RotatingFileHandler
import os

# 🟩 Tạo thư mục logs nếu chưa có
if not os.path.exists("logs"):
    os.makedirs("logs")

# 🟩 Cấu hình logger
log_file = os.path.join("logs", "app.log")
handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)

# 🟩 Gắn handler vào root logger
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)
