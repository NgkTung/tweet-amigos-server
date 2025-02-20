from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from supabase import create_client
from utils.cloudinary import upload_image, delete_image
from dotenv import load_dotenv
from passlib.context import CryptContext
from datetime import datetime, timedelta
from uuid import UUID

from models.User import UserBase, UserCreate, UserResponse, UserAccess, UserFollowerResponse, SignInRequest
from models.Tweet import TweetResponse, TweetUserResponse
import os
import jwt

load_dotenv()


SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

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

def create_access_token(data: dict, expires_delta: timedelta = None):
	to_encode = data.copy()
	if expires_delta:
		expire = datetime.now() + expires_delta
	else:
		expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
	to_encode.update({"exp": expire})

	encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
	return encoded_jwt

@app.post("/signup")
async def sign_up(request: UserCreate):
	try:
		# Hash the password before sending it to Supabase (if you're using a custom DB, not Supabase auth)
		hashed_password = hash_password(request.password)

		# Use Supabase Auth to create the user (Supabase already handles password hashing)
		response = supabase.auth.sign_up({
			"email": request.email,
			"password": request.password,  # Supabase handles hashing internally
		})

		# Check if response contains error
		if not response:
			raise HTTPException(status_code=400, detail=response["error"]["message"])

		# Extract user info from the response
		user = response.user
		
		if not user:
			raise HTTPException(status_code=400, detail="User creation failed, no user data found")

		user_id = user.id

		user_data = {
			"id": user_id,
			"username": request.username,
			"email": request.email,
			"password": hashed_password,
			"role_id": "d380cc38-cd59-4e4a-8f5d-4a6afec84fca"
		}

		insert_response = supabase.table('users').insert(user_data).execute()

		
		if not insert_response:
			raise HTTPException(status_code=500, detail="Error saving user data")
		
		return {"message": "Sign-up successful!"}

	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/signin")
async def sign_in(request: SignInRequest):
	try:
		# Directly check the password using Supabase Auth (it manages password hashing)
		response = supabase.auth.sign_in_with_password({
			"email": request.email,
			"password": request.password,
		})

		if not response:
			raise HTTPException(status_code=400, detail=response["error"]["message"])
		
		user_data = supabase.table("users").select("*").eq("id", response.user.id).execute()

		#Generate JWT token
		access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
		access_token = create_access_token(
			data={"sub": user_data.data[0]["id"]},
			expires_delta=access_token_expires
		)

		return {"message": "Sign-in successful!", "token": access_token}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@app.post("/signout")
async def sign_out():
	try:
		supabase.auth.sign_out()

		return {"message": "Successfully signed out!"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@app.get("/users")
async def get_users(user_id: Optional[str] = None, page: int = 1, page_size: int = 10):
	offset = (page - 1) * page_size

	response = supabase \
		.from_("users") \
		.select("*") \
		.order("created_at", desc=True) \
		.range(offset, offset + page_size - 1) \
		.execute()
	
	if not response.data:
		raise HTTPException(status_code=400, detail="Error fetching users")
	
	users = []
	for user in response.data:
		tweet_count_response = supabase.from_("tweets").select("*", count= "exact").eq("user_id", user["id"]).execute()
		tweet_count = tweet_count_response.count

		follower_count_response = supabase.from_("user_followers").select("*", count="exact").eq("user_id", user["id"]).execute()
		follower_count = follower_count_response.count

		following_count_response = supabase.from_("user_followers").select("*", count="exact").eq("follower_id", user["id"]).execute()
		following_count = following_count_response.count

		is_followed = None
		if user_id:
			is_followed_response = supabase \
				.from_("user_followers") \
				.select("id") \
				.eq("follower_id", user_id) \
				.eq("user_id", user["id"]) \
				.execute()
				
			is_followed = bool(is_followed_response.data)

		user_data = UserResponse(
			id=user["id"],
			email=user["email"],
			username=user["username"],
			bio=user["bio"],
			profile_image_url=user["profile_image_url"],
			background_image_url=user["background_image_url"],
			created_at=user["created_at"],
			tweet_count=tweet_count,
			follower_count=follower_count,
			following_count=following_count,
			is_followed=is_followed
		)
		users.append(user_data)
	return {"data": users, "page": page, "page_size": page_size}

# Get user
@app.post("/user", response_model=UserResponse)
async def get_user(request: UserAccess):
	try:
		payload = jwt.decode(request.access_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
		user_id = payload.get("sub")
		
		response = supabase.table("users").select("*").eq("id", user_id).execute()
		user = response.data

		if not user:
			raise HTTPException(status_code=400, detail="User not found!")
		
		 # Fetch tweet count for the user
		tweet_count_response = supabase.from_("tweets").select("*", count= "exact").eq("user_id", user_id).execute()
		tweet_count = tweet_count_response.count

		# Fetch followers count for the user
		follower_count_response = supabase.from_("user_followers").select("*", count="exact").eq("user_id", user_id).execute()
		follower_count = follower_count_response.count

		# Fetch following count for the user
		following_count_response = supabase.from_("user_followers").select("*", count="exact").eq("follower_id", user_id).execute()
		following_count = following_count_response.count
		
		user_data = UserResponse(
			id=user[0]["id"],
			email=user[0]["email"],
			username=user[0]["username"],
			bio=user[0]["bio"],
			profile_image_url=user[0]["profile_image_url"],
			background_image_url=user[0]["background_image_url"],
			created_at=user[0]["created_at"],
			tweet_count=tweet_count,
			follower_count=follower_count,
			following_count=following_count
		)
		return user_data
	except jwt.ExpiredSignatureError:
		raise HTTPException(status_code=401, detail="Token has expired")
	except jwt.PyJWTError:
		raise HTTPException(status_code=401, detail="Invalid token")

# Get user by id
@app.get("/user/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, follower_id: Optional[str] = None):
	response = supabase.table("users").select("*").eq("id", user_id).execute()
	user = response.data

	if not user:
		raise HTTPException(status_code=404, detail="User not found!")
		
	# Fetch tweet count for the user
	tweet_count_response = supabase.from_("tweets").select("*", count= "exact").eq("user_id", user_id).execute()
	tweet_count = tweet_count_response.count

	# Fetch followers count for the user
	follower_count_response = supabase.from_("user_followers").select("*", count="exact").eq("user_id", user_id).execute()
	follower_count = follower_count_response.count
		
	# Fetch following count for the user
	following_count_response = supabase.from_("user_followers").select("*", count="exact").eq("follower_id", user_id).execute()
	following_count = following_count_response.count

	is_followed = None
	if follower_id:
		is_followed_response = supabase \
			.from_("user_followers") \
			.select("id") \
			.eq("follower_id", follower_id) \
			.eq("user_id", user_id) \
			.execute()
				
		is_followed = bool(is_followed_response.data)

	user_data = UserResponse(
		id=user[0]["id"],
		email=user[0]["email"],
		username=user[0]["username"],
		bio=user[0]["bio"],
		profile_image_url=user[0]["profile_image_url"],
		background_image_url=user[0]["background_image_url"],
		created_at=user[0]["created_at"],
		tweet_count=tweet_count,
		follower_count=follower_count,
		following_count=following_count,
		is_followed=is_followed
	)
	return user_data

# Get all tweets of user by user id
@app.get("/user/{user_id}/tweets")
async def get_tweets_by_user_id(user_id: str, page: Optional[int] = 1, page_size: Optional[int] = 10):
	existing_user_response = supabase \
		.table("users") \
		.select("*") \
		.eq("id", user_id) \
		.execute()
	
	if not existing_user_response.data:
		raise HTTPException(status_code=404, detail="User not found!")
	
	# Calculate offset
	offset = (page - 1) * page_size
	
	user_tweets_response = supabase \
		.from_("tweets") \
		.select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url)") \
		.eq("user_id", user_id) \
		.order("created_at", desc=True) \
		.range(offset, offset + page_size - 1) \
		.execute()
	
	if not user_tweets_response.data:
		return {"data": [], "page": page, "page_size": page_size, "tweet_count": 0}
	
	tweets = []
	for tweet in user_tweets_response.data:
		# Count the number of users who liked this tweet
		likes_count_response = supabase \
			.from_("tweet_likes") \
			.select("id") \
			.eq("tweet_id", tweet["id"]) \
			.execute()
		
		likes_count = len(likes_count_response.data)

		# Count the number of retweets for this tweet
		retweet_count_response = supabase \
			.from_("tweets") \
			.select("id") \
			.eq("retweet_id", tweet["id"]) \
			.execute()

		retweet_count = len(retweet_count_response.data)  # Get the count of retweets

		reply_to = None
		if tweet["retweet_id"]:
			reply_to_response = supabase \
				.from_("tweets") \
				.select("users(email)") \
				.eq("id", tweet["retweet_id"]) \
				.execute()
		
			if reply_to_response.data:
				reply_to = reply_to_response.data[0]["users"]["email"]

		is_liked = False

		if user_id:
			is_liked_response = supabase \
				.from_("tweet_likes") \
				.select("id") \
				.eq("tweet_id", tweet["id"]) \
				.eq("user_id", user_id) \
				.execute()
			
			is_liked = bool(is_liked_response.data)

		# Get the user data for this tweet
		user = tweet["users"]
		tweet_data = TweetResponse(
			id=tweet["id"],
			content=tweet["content"],
			user_id=tweet["user_id"],
			retweet_id=tweet.get("retweet_id"),
			image_url=tweet.get("image_url"),
			created_at=tweet["created_at"],
			user=UserBase(
				id=user["id"], 
				username=user["username"], 
				email=user["email"], 
				profile_image_url=user['profile_image_url']
			),
			retweet_count=retweet_count,
			likes_count=likes_count,
			is_liked=is_liked,
			reply_to=reply_to
		)
		tweets.append(tweet_data)
	return  {"data": tweets, "page": 1, "page_size": page_size, "tweet_count": len(tweets)}

# Toggle follow user
@app.post("/user/{user_id}")
async def toggle_follow_user(user_id: str, request: UserFollowerResponse):
	# Check if follower already follow the user
	existing_follow = supabase \
		.table("user_followers") \
		.select("*") \
		.eq("user_id", user_id) \
		.eq("follower_id", request.follower_id) \
		.execute()
	# If yes, then un-follow
	if existing_follow.data:
		response = supabase.table("user_followers") \
			.delete() \
			.eq("user_id", user_id) \
			.eq("follower_id", request.follower_id) \
			.execute()
		if not response.data:
			raise HTTPException(status_code=500, detail="Failed to un-follow the user")
		return {"message": "Un-follow user successfully!"}
	# If not, then follow user
	else:
		response = supabase \
		.table("user_followers") \
		.insert({"user_id": user_id, "follower_id": str(request.follower_id)}) \
		.execute()
		if not response.data:
			raise HTTPException(status_code=500, detail="Failed to follow the user")
		return {"message": "Follow user successfully!"}

# Update user
@app.put("/user/{user_id}")
async def update_user(user_id: str,
	username: str = Form(...),
	bio: Optional[str] = Form(None),
	profile_image: Optional[UploadFile] = File(None),
	background_image: Optional[UploadFile] = File(None)):

	profile_image_url = None
	background_image_url = None

	# Upload the profile image if provided
	if profile_image:
		profile_image_url = upload_image(profile_image.file, folder="profile_images")

	# Upload the background image if provided
	if background_image:
		background_image_url = upload_image(background_image.file, folder="background_images")

	# Fetch the existing user data from the database
	response = supabase.table("users").select("*").eq("id", user_id).execute()
	if not response.data:
		raise HTTPException(status_code=404, detail="User not found")
	
	user_data = response.data[0]
	
	# Prepare the data to update the user
	user_update_data = {
		"username": username,
		"bio": bio if bio else None,
	}
	# If profile image is changed, delete the old one from Cloudinary
	if profile_image and user_data["profile_image_url"]:
		try:
			delete_image(user_data["profile_image_url"])
		except:
			raise HTTPException(status_code=500, detail="Failed to delete the profile image")


	# If background image is changed, delete the old one from Cloudinary
	if background_image and user_data["background_image_url"]:
		try:
			delete_image(user_data["background_image_url"])
		except:
			raise HTTPException(status_code=500, detail="Failed to delete the background image")

	# Update profile image URL if provided
	if profile_image_url:
		user_update_data["profile_image_url"] = profile_image_url

	# Update background image URL if provided
	if background_image_url:
		user_update_data["background_image_url"] = background_image_url

	# Update the user record in the database
	update_response = supabase.table("users").update(user_update_data).eq("id", user_id).execute()
	
	# Check if the update was successful
	if not update_response.data:
		raise HTTPException(status_code=500, detail="Failed to update user")

	return {"message": "User updated successfully", "data": update_response.data}

# Get all followers of user by user id
@app.get("/user/{user_id}/followers")
async def get_user_followers(user_id: str, page: int = 1, page_size: int = 10):
	offset = (page - 1) * page_size

	existing_user_response = supabase \
		.table("users") \
		.select("*") \
		.eq("id", user_id) \
		.execute()
	
	if not existing_user_response.data:
		raise HTTPException(status_code=404, detail="User not found")
	
	user_followers_response = supabase \
		.from_("user_followers") \
		.select("follower_id") \
		.eq("user_id", user_id) \
		.execute()
	
	if not user_followers_response.data:
		return {"data": [], "page": page, "page_size": page_size, "count": 0}
	
	followers = []

	for response in user_followers_response.data:
		follower_response = supabase \
			.table("users") \
			.select("*") \
			.eq("id", response["follower_id"]) \
			.range(offset, offset + page_size - 1) \
			.execute()
		if not follower_response.data:
			raise HTTPException(status_code=500, detail="Failed while fetching follower")
		follower_data=follower_response.data
		data = UserResponse(
			id=follower_data[0]["id"],
			email=follower_data[0]["email"],
			username=follower_data[0]["username"],
			bio=follower_data[0]["bio"],
			profile_image_url=follower_data[0]["profile_image_url"],
			background_image_url=follower_data[0]["background_image_url"],
			created_at=follower_data[0]["created_at"],
		)
		followers.append(data)
	return {"data": followers, "page": page, "page_size": page_size, "count": len(followers)}

# Get all following of user by user id
@app.get("/user/{user_id}/followings")
async def get_user_following(user_id: str, page: int = 1, page_size: int = 10):
	offset = (page - 1) * page_size

	existing_user_response = supabase \
		.table("users") \
		.select("*") \
		.eq("id", user_id) \
		.execute()
	
	if not existing_user_response.data:
		raise HTTPException(status_code=404, detail="User not found")
	
	user_following_response = supabase \
		.from_("user_followers") \
		.select("user_id") \
		.eq("follower_id", user_id) \
		.execute()
	
	if not user_following_response.data:
		return {"data": [], "page": page, "page_size": page_size, "count": 0}
	
	followings = []

	for response in user_following_response.data:
		follower_response = supabase \
			.table("users") \
			.select("*") \
			.eq("id", response["user_id"]) \
			.range(offset, offset + page_size - 1) \
			.execute()
		if not follower_response.data:
			raise HTTPException(status_code=500, detail="Failed while fetching follower")
		following_data=follower_response.data
		data = UserResponse(
			id=following_data[0]["id"],
			email=following_data[0]["email"],
			username=following_data[0]["username"],
			bio=following_data[0]["bio"],
			profile_image_url=following_data[0]["profile_image_url"],
			background_image_url=following_data[0]["background_image_url"],
			created_at=following_data[0]["created_at"],
		)
		followings.append(data)
	return {"data": followings, "page": page, "page_size": page_size, "count": len(followings)}

# Get all tweets
@app.get("/tweets")
async def get_tweets(user_id: Optional[str] = None, page: int = 1, page_size: int = 10, no_retweets: Optional[bool] = False):
	# Fetch all tweets along with user details
	offset = (page - 1) * page_size

	query = supabase \
		.from_("tweets") \
		.select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url)") \
		.order("created_at", desc=True) \
		.range(offset, offset + page_size - 1) \
		
	if no_retweets is True:
		query = query.is_("retweet_id", None)
	
	tweets_data = query.execute()

	if not tweets_data.data:
		return {"data": [], "page": page, "page_size": page_size, "tweet_count": 0}

	tweets = []
	for tweet in tweets_data.data:
		# Count the number of users who liked this tweet
		likes_count_response = supabase \
			.from_("tweet_likes") \
			.select("id") \
			.eq("tweet_id", tweet["id"]) \
			.execute()
		
		likes_count = len(likes_count_response.data)

		# Count the number of retweets for this tweet
		retweet_count_response = supabase \
			.from_("tweets") \
			.select("id") \
			.eq("retweet_id", tweet["id"]) \
			.execute()

		retweet_count = len(retweet_count_response.data)  # Get the count of retweets

		reply_to = None
		if tweet["retweet_id"]:
			reply_to_response = supabase \
				.from_("tweets") \
				.select("users(email)") \
				.eq("id", tweet["retweet_id"]) \
				.execute()
		
			if reply_to_response.data:
				reply_to = reply_to_response.data[0]["users"]["email"]

		is_liked = False

		if user_id:
			is_liked_response = supabase \
				.from_("tweet_likes") \
				.select("id") \
				.eq("tweet_id", tweet["id"]) \
				.eq("user_id", user_id) \
				.execute()
			
			is_liked = bool(is_liked_response.data)

		# Get the user data for this tweet
		user = tweet["users"]
		tweet_data = TweetResponse(
			id=tweet["id"],
			content=tweet["content"],
			user_id=tweet["user_id"],
			retweet_id=tweet.get("retweet_id"),
			image_url=tweet.get("image_url"),
			created_at=tweet["created_at"],
			user=UserBase(
				id=user["id"], 
				username=user["username"], 
				email=user["email"], 
				profile_image_url=user['profile_image_url']
			),
			retweet_count=retweet_count,
			likes_count=likes_count,
			is_liked=is_liked,
			reply_to=reply_to
		)
		tweets.append(tweet_data)

	return {"data": tweets, "page": page, "page_size": page_size, "tweet_count": len(tweets)}


# Get tweet by ID
@app.get("/tweets/{tweet_id}", response_model=TweetResponse)
async def get_tweet_by_id(tweet_id: str, user_id: Optional[UUID] = None):
	response = supabase \
	.table("tweets") \
	.select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url)") \
	.eq("id", tweet_id) \
	.execute()
	tweet= response.data
	
	if not tweet:
		raise HTTPException(status_code=404, detail="Tweet not found")
	
	retweet_count_response = supabase \
		.table("tweets") \
		.select("id") \
		.eq("retweet_id", tweet_id) \
		.execute()

	retweet_count = len(retweet_count_response.data)

	# Count the number of users who liked this tweet
	likes_count_response = supabase \
		.from_("tweet_likes") \
		.select("id") \
		.eq("tweet_id", tweet_id) \
		.execute()
		
	likes_count = len(likes_count_response.data)

	reply_to = None
	if tweet[0]["retweet_id"]:
		reply_to_response = supabase \
			.from_("tweets") \
			.select("users(email)") \
			.eq("id", tweet[0]["retweet_id"]) \
			.execute()
		print(reply_to_response.data)
		if reply_to_response.data:
			reply_to = reply_to_response.data[0]["users"]["email"]

	is_liked = False

	if user_id:
		is_liked_response = supabase \
				.from_("tweet_likes") \
				.select("id") \
				.eq("tweet_id", tweet_id) \
				.eq("user_id", user_id) \
				.execute()
				
		is_liked = bool(is_liked_response.data)

	user = tweet[0]["users"]
	tweet_data = TweetResponse(
			id=tweet[0]["id"],
			content=tweet[0]["content"],
			user_id=tweet[0]["user_id"],
			retweet_id=tweet[0].get("retweet_id"),
			image_url=tweet[0].get("image_url"),
			created_at=tweet[0]["created_at"],
			user=UserBase(id=user["id"], username=user["username"], email=user["email"], profile_image_url=user['profile_image_url']),
			retweet_count=retweet_count,
			likes_count=likes_count,
			is_liked=is_liked,
			reply_to=reply_to
		)
	return tweet_data

# Get retweets of tweet
@app.get("/tweets/{tweet_id}/retweets")
async def get_retweets(tweet_id: str, user_id: Optional[str] = None, page: int = 1, page_size: int = 10):
	# Calculate offset
	offset = (page - 1) * page_size
	
	# Fetch retweets for the tweet
	response = supabase \
		.table("tweets") \
		.select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url)") \
		.eq("retweet_id", tweet_id) \
		.range(offset, offset + page_size - 1) \
		.execute()
	
	retweets = response.data
	
	if not retweets:
		raise HTTPException(status_code=404, detail="No retweets found")

	reply_to_response = supabase \
		.from_("tweets") \
		.select("users(email)") \
		.eq("id", tweet_id) \
		.execute()
	
	reply_to = None
	if reply_to_response.data:
		reply_to = reply_to_response.data[0]["users"]["email"]

	retweets_data = []

	for retweet in retweets:		
		retweet_count_response = supabase \
			.table("tweets") \
			.select("id") \
			.eq("retweet_id", retweet["id"]) \
			.execute()

		retweet_count = len(retweet_count_response.data) 

		# Count the number of users who liked this tweet
		likes_count_response = supabase \
			.from_("tweet_likes") \
			.select("id") \
			.eq("tweet_id", retweet["id"]) \
			.execute()
			
		likes_count = len(likes_count_response.data)

		is_liked = False

		if user_id:
			is_liked_response = supabase \
						.from_("tweet_likes") \
						.select("id") \
						.eq("tweet_id", retweet["id"]) \
						.eq("user_id", user_id) \
						.execute()
					
			is_liked = bool(is_liked_response.data)
		
		retweet_data = \
			TweetResponse(
				id=retweet["id"],
				content=retweet["content"],
				user_id=retweet["user_id"],
				retweet_id=retweet.get("retweet_id"),
				image_url=retweet.get("image_url"),
				created_at=retweet["created_at"],
				user=UserBase(
					id=retweet["users"]["id"],
					username=retweet["users"]["username"],
					email=retweet["users"]["email"],
					profile_image_url=retweet["users"]["profile_image_url"]
				),
				retweet_count=retweet_count,
				likes_count=likes_count,
				is_liked=is_liked,
				reply_to=reply_to
			)
		retweets_data.append(retweet_data)
	
	return {"data": retweets_data, "page": page, "page_size": page_size}

# Toggle like a tweet
@app.post("/tweets/{tweet_id}/toggle-like")
async def toggle_like_tweet(tweet_id: str, request: TweetUserResponse):
	try:
		# Check if the user has already likes the tweet
		existing_like = supabase \
			.from_("tweet_likes") \
			.select("*") \
			.eq("tweet_id", tweet_id) \
			.eq("user_id", request.user_id) \
			.execute()
		if existing_like.data:
			# User has already liked the tweet, then unlike it
			response = supabase \
				.from_("tweet_likes") \
				.delete() \
				.eq("tweet_id", tweet_id) \
				.eq("user_id", request.user_id) \
				.execute()
			if not response.data:
				raise HTTPException(status_code=500, detail="Failed to unlike the tweet")
			return {"message": "Tweet unliked successfully!"}
		else:
			# User hasn't liked the tweet yet, so like it
			response = supabase \
				.from_("tweet_likes") \
				.insert({"tweet_id": tweet_id, "user_id": str(request.user_id)}) \
				.execute()
			
			if not response.data:
				raise HTTPException(status_code=500, detail="Failed to like the tweet")
			return {"message": "Tweet liked successfully!"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

# Check if user already like a tweet
@app.post("/tweets/{tweet_id}/like")
async def check_like_status(tweet_id: str, request: TweetUserResponse):
	try:
		# Check if the user has already likes the tweet
		existing_like = supabase \
			.from_("tweet_likes") \
			.select("*") \
			.eq("tweet_id", tweet_id) \
			.eq("user_id", request.user_id) \
			.execute()
		if not existing_like.data:
			return {"message": "User is not like this tweet yet", "status": False}
		else:
			return {"message": "User is already like this tweet", "status": True}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/tweets")
async def create_tweet(
	content: str = Form(...),
	user_id: str = Form(...),
	retweet_id: Optional[str] = Form(None),
	image: Optional[UploadFile] = None
):
	try:
		# Initialize image_url as None
		image_url = None
		
		# Handle image upload if provided
		if image:
			image_url = upload_image(image.file, folder="tweet_images")
		
		# If retweet_id is provided, check if the original tweet exists
		if retweet_id:
			response = supabase.table("tweets").select("*").eq("id", retweet_id).execute()
			if not response.data:
				return {"error": "The original tweet does not exist."}
		
		# Prepare the tweet data
		tweet_data = {
			"user_id": user_id,
			"content": content,
			"image_url": image_url,
			"retweet_id": retweet_id if retweet_id is not None else None
		}

		# Insert the tweet data into the database
		response = supabase.table("tweets").insert(tweet_data).execute()

		# Check for errors in the response
		if not response:
			return HTTPException(status_code=400, detail="Failed to create tweet")
		
		# If successful, return a success message along with the tweet data
		return {
			"message": "Tweet created successfully",
			"tweet": response.data
		}
	
	except RuntimeError as e:
		return {"error": str(e)}

@app.delete("/tweets/{tweet_id}")
async def delete_tweet(tweet_id: str):
	existing_tweet_response = supabase \
		.from_("tweets") \
		.select("*") \
		.eq("id", tweet_id) \
		.execute()
	if not existing_tweet_response.data:
		raise HTTPException(status_code=404, detail="Tweet not found")
	
	response = supabase \
		.from_("tweets") \
		.delete() \
		.eq("id", tweet_id) \
		.execute()

	if not response.data:
		raise HTTPException(status_code=500, detail="Failed to delete tweet")
	
	return {"message": "Tweet deleted successfully"}