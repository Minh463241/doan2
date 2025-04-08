import cloudinary.uploader
from config import Config

cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET,
    secure=True
)

def upload_image(file, folder="avatars"):
    result = cloudinary.uploader.upload(file, folder=folder)
    return result["secure_url"]