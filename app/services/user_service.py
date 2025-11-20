from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password

async def get_user_by_email(db: AsyncSession, email:str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, id:int):
    result = await db.execute(select(User).where(User.id == id))
    return result.scalar_one_or_none()

async def get_all_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()

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