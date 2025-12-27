from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password
from app.core.jwt_config import create_access_token, create_refresh_token
from app.services.user_queries import get_user_by_email, get_user_by_id
from app.core.security import verify_password
from fastapi import HTTPException
from sqlalchemy.sql import func

async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str
):
    user = await get_user_by_email(db, email)
    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user

async def create_user(db: AsyncSession, data: UserCreate):
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise ValueError("User already Exists")
    
    user = User(
        email = data.email,
        name = data.name,
        password_hash = hash_password(data.password)
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def edit_user(db : AsyncSession, data ,user_id: int):
    user = await get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(404, "User does not exist")
    
    if data.name:
        user.name = data.name

    if data.email:
        user.email = data.email

    #TODO: add phone number support

    await db.commit()
    await db.refresh(user)

    return user

async def login_user_service(
    db: AsyncSession,
    email: str,
    password: str
):
    user = await authenticate_user(db, email, password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    user.refresh_token = refresh_token
    user.last_login_at = func.now()

    await db.commit()
    await db.refresh(user)

    return user, access_token, refresh_token
