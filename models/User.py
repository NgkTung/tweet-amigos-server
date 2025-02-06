from pydantic import BaseModel, HttpUrl
from typing import Optional

from pydantic import BaseModel, HttpUrl
from typing import Optional
from uuid import UUID

# Shared fields for user models
class UserBase(BaseModel):
    email: str
    username: str
    bio: Optional[str] = None
    role: str = 'user'  # Default role is 'user'
    profile_image_url: Optional[HttpUrl] = None
    background_image_url: Optional[HttpUrl] = None


# Request model for creating a user
class UserCreate(UserBase):
    username: str
    email: str
    password: str  # Password is required only when creating a user

# Response model for returning user data
class UserResponse(UserBase):
    id: UUID  # Include id in the response model
    
class UserAccess(BaseModel):
    access_token: str

# Model for updating user info (e.g., partial update)
class UserUpdate(UserBase):
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None  # Optional during update
    bio: Optional[str] = None
    role: Optional[str] = None
    profile_image_url: Optional[HttpUrl] = None
    background_image_url: Optional[HttpUrl] = None
    
class SignInRequest(BaseModel):
    email: str
    password: str
