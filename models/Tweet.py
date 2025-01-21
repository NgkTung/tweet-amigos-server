from pydantic import BaseModel, HttpUrl
from typing import Optional
from .User import UserBase
from datetime import datetime

class Tweet(BaseModel):
    id: Optional[int]
    content: str
    user_id: int
    retweet_id: Optional[int]
    image_url: Optional[HttpUrl]
    created_at: Optional[datetime]
    user: UserBase