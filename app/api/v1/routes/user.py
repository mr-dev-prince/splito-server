from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.user_queries import get_all_users
from app.core.utils import get_user_total_balance

router = APIRouter()

@router.get("/",)
async def get_all(db:AsyncSession = Depends(get_db)):
    users = await get_all_users(db)
    return users

@router.get("/{user_id}/balance")
async def user_balance(user_id: int, db: AsyncSession = Depends(get_db)):
    bal = await get_user_total_balance(db, user_id=user_id)
    return {"user_id": user_id, "amount": float(bal)}