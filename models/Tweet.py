from pydantic import BaseModel, HttpUrl
from typing import Optional
from .User import UserBase
from datetime import datetime

# TweetCreate for creating a new tweet
class TweetCreate(BaseModel):
    content: str
    user_id: int
    retweet_id: Optional[int] = None
    image_url: Optional[HttpUrl] = None

# TweetUpdate for updating an existing tweet
class TweetUpdate(BaseModel):
    content: Optional[str] = None
    retweet_id: Optional[int] = None
    image_url: Optional[HttpUrl] = None

# TweetResponse for returning tweet details (i.e., after creation)
class TweetResponse(BaseModel):
    id: int
    content: str
    user_id: int
    retweet_id: Optional[int]
    image_url: Optional[HttpUrl]
    created_at: Optional[datetime]
    user: UserBase

# Tweet model (you may use this for internal representations in DB models)
class Tweet(BaseModel):
    id: Optional[int]
    content: str
    user_id: int
    retweet_id: Optional[int]
    image_url: Optional[HttpUrl]
    created_at: Optional[datetime]
    user: UserBase
    