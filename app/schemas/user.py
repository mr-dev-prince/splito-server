from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email:EmailStr
    name:str

class UserCreate(UserBase):
    password:str

class UserLogin(UserBase):
    email:EmailStr
    password:str

class UserOut(UserBase):
    id:int
    email:EmailStr
    name:str
    created_at:datetime
    is_active:bool

    class Config:
        from_attributes = True