from pydantic import BaseModel, HttpUrl
from typing import Optional
from .User import UserBase
from datetime import datetime
from uuid import UUID

# TweetCreate for creating a new tweet
class TweetCreate(BaseModel):
    content: str
    user_id: UUID
    retweet_id: Optional[str] = None
    image_url: Optional[HttpUrl] = None

# TweetUpdate for updating an existing tweet
class TweetUpdate(BaseModel):
    content: Optional[str] = None
    retweet_id: Optional[str] = None
    image_url: Optional[HttpUrl] = None

# TweetResponse for returning tweet details (i.e., after creation)
class TweetResponse(BaseModel):
    id: UUID
    content: str
    user_id: UUID
    retweet_id: Optional[str]
    image_url: Optional[HttpUrl]
    created_at: Optional[datetime]
    user: UserBase
    retweet_count: int
    likes_count: int
    is_liked: bool
    reply_to: Optional[str] = None

# Tweet model (you may use this for internal representations in DB models)
class Tweet(BaseModel):
    id: Optional[UUID]
    content: str
    user_id: UUID
    retweet_id: Optional[str]
    image_url: Optional[HttpUrl]
    created_at: Optional[datetime]
    user: UserBase
    
class TweetUserResponse(BaseModel):
    user_id: UUID
    