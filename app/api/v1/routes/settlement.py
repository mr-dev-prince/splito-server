from fastapi import APIRouter, Depends
from app.schemas.user import AuthUser
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user, check_group_membership
from app.services.settlement_service import admin_group_settlements

router = APIRouter()


@router.get("/admin-groups")
async def get_settlements(
    db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)
):
    return await admin_group_settlements(db, user.id)
