import cloudinary
import cloudinary.uploader
import cloudinary.api
import os

CLOUDINARY_NAME = os.getenv('CLOUDINARY_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

cloudinary.config(
	cloud_name=CLOUDINARY_NAME, 
	api_key=CLOUDINARY_API_KEY, 
	api_secret=CLOUDINARY_API_SECRET,
	secure=True
)

def upload_image(image_file, folder):
	try:
		# Upload the image with transformation to limit the width to 1920px
		result = cloudinary.uploader.upload(
			image_file,
			folder=folder,
			transformation=[
				{'width': 1920, 'crop': 'limit'}  # Ensures the image width is limited to 1920px
			]
		)
		return result["secure_url"]
	except Exception as e:
		raise RuntimeError(f"Image upload failed: {str(e)}")

# Function to delete image from Cloudinary
def delete_image(image_url: str):
	public_id = None
	if image_url:
		if "res.cloudinary.com" not in image_url:
			print("Return")
			return
		public_id = '/'.join(image_url.split('/upload/')[1].split('.')[0].split('/')[1:])
	
	if public_id:
		cloudinary.api.delete_resources([public_id])