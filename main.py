from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from supabase import create_client
from utils.cloudinary import upload_image
from dotenv import load_dotenv
from models.User import UserBase
from models.Tweet import Tweet
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

@app.get("/tweets", response_model=List[Tweet])
async def get_tweets():
    tweets_data = supabase \
        .from_("tweets") \
        .select("id, content, user_id, retweet_id, image_url, created_at, users(id, username, email, profile_image_url, background_image_url)") \
        .execute()
    print(tweets_data)

    if not tweets_data.data:
        raise HTTPException(status_code=400, detail="Error fetching tweets")

    # Return list of tweets with user info
    tweets = []
    for tweet in tweets_data.data:
        user = tweet["users"]
        tweet_data = Tweet(
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