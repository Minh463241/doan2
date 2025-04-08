from flask import Blueprint, request
from utils.upload_cloudinary import upload_image

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/avatar', methods=['POST'])
def upload_avatar():
    if 'file' not in request.files:
        return "Không có file", 400
    file = request.files['file']
    url = upload_image(file, folder="avatars")
    return {"url": url}