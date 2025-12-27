from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User

async def get_user_by_id(db: AsyncSession, user_id: int):
    res = await db.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str):
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()

async def get_all_users(db: AsyncSession):
    res = await db.execute(select(User))
    return res.scalars().all()
