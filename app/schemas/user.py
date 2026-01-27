from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    name: str


class AuthUser(BaseModel):
    id: int
    clerk_user_id: str
    email: str | None = None
    is_active: bool = True

    class Config:
        frozen = True


class SetPinRequest(BaseModel):
    pin: str
