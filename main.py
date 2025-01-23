from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from supabase import create_client
from utils.cloudinary import upload_image
from dotenv import load_dotenv
from passlib.context import CryptContext

from models.User import UserBase, UserCreate
from models.Tweet import TweetResponse
import os

load_dotenv()


SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

origins = [
	"*"
]

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
	return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
	return pwd_context.verify(plain_password, hashed_password)

@app.post("/signup")
async def sign_up(request: UserCreate):
	try:
		# Hash the password before sending it to Supabase (if you're using a custom DB, not Supabase auth)
		hashed_password = hash_password(request.password)

		# Use Supabase Auth to create the user (Supabase already handles password hashing)
		response = supabase.auth.sign_up({
			"username": request.username,
			"email": request.email,
			"password": hashed_password,  # Supabase handles hashing internally
		})

		if not response:
			raise HTTPException(status_code=400, detail=response["error"]["message"])

		return {"message": "Sign-up successful!"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/signin")
async def sign_in(request: SignInRequest):
    try:
        # Directly check the password using Supabase Auth (it manages password hashing)
        response = supabase.auth.sign_in({
            "email": request.email,
            "password": request.password,
        })

        if not response:
            raise HTTPException(status_code=400, detail=response["error"]["message"])

        return {"message": "Sign-in successful!", "user": response.get("user")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/signout")
async def sign_out():
    try:
        response = supabase.auth.sign_out()

        if not response:
            raise HTTPException(status_code=400, detail=response["error"]["message"])

        return {"message": "Successfully signed out!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get all tweets
@app.get("/tweets", response_model=List[TweetResponse])
async def get_tweets():
	tweets_data = supabase \
		.from_("tweets") \
		.select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url)") \
		.order("created_at", desc=True) \
		.execute()

	if not tweets_data.data:
		raise HTTPException(status_code=400, detail="Error fetching tweets")

	# Return list of tweets with user info
	tweets = []
	for tweet in tweets_data.data:
		user = tweet["users"]
		tweet_data = TweetResponse(
			id=tweet["id"],
			content=tweet["content"],
			user_id=tweet["user_id"],
			retweet_id=tweet.get("retweet_id"),
			image_url=tweet.get("image_url"),
			created_at=tweet["created_at"],
			user=UserBase(id=user["id"], username=user["username"], email=user["email"], profile_image_url=user['profile_image_url'])
		)
		tweets.append(tweet_data)
	return tweets

# Get tweet by ID
@app.get("/tweets/{tweet_id}", response_model=TweetResponse)
async def get_tweet_by_id(tweet_id: int):
	response = supabase \
	.table("tweets") \
	.select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url)") \
	.eq("id", tweet_id) \
	.execute()
	tweet= response.data
	
	if not tweet:
		raise HTTPException(status_code=404, detail="Tweet not found")

	user = tweet[0]["users"]
	tweet_data = TweetResponse(
			id=tweet[0]["id"],
			content=tweet[0]["content"],
			user_id=tweet[0]["user_id"],
			retweet_id=tweet[0].get("retweet_id"),
			image_url=tweet[0].get("image_url"),
			created_at=tweet[0]["created_at"],
			user=UserBase(id=user["id"], username=user["username"], email=user["email"], profile_image_url=user['profile_image_url'])
		)
	return tweet_data


@app.post("/tweets")
async def create_tweet(
	content: str = Form(...),
	user_id: int = Form(...),
	retweet_id: Optional[int] = Form(None),
	image: Optional[UploadFile] = None
):
	try:
		image_url = None
		if image:
			image_url = upload_image(image.file, folder="tweet_images")
		
		if retweet_id:
			response = supabase.table("tweets").select("*").eq("id", retweet_id).execute()
			
			if not response.data:
				return{"error": "The original tweet does not exist."}
		
		tweet_data = {
			"user_id": user_id,
			"content": content,
			"image_url": image_url
		}

		response = supabase.table("tweets").insert(tweet_data).execute()

		if response:
			return {
			"message": "Tweet created successfully",
			"tweet": response.data
		}
		else:
			raise RuntimeError("Failed to create tweet: " + response.error)  
		
	except RuntimeError as e:
		return {"error": str(e)}