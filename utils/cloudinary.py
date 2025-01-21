import cloudinary
import cloudinary.uploader
import os

CLOUDINARY_NAME = os.getenv('CLOUDINARY_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

cloudinary.config(
    cloud_name = CLOUDINARY_NAME, 
    api_key = CLOUDINARY_API_KEY, 
    api_secret = CLOUDINARY_API_SECRET,
    secure=True
)

def upload_image(image_file, folder):
    try:
        result = cloudinary.uploader.upload(image_file, folder=folder)
        return result["secure_url"]
    except Exception as e:
        raise RuntimeError(f"Image upload failed: {str(e)}")