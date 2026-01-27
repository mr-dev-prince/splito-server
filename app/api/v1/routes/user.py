from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.user_service import (
    set_pin_service,
    verify_pin_service,
    deactivate_pin_service,
    get_user_data,
)
from app.core.dependencies import get_current_user, get_db
from app.schemas.user import AuthUser, SetPinRequest


router = APIRouter()


# working fine
@router.get("/me")
async def get_user(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    return await get_user_data(db, user.id)


# working fine
@router.post("/security/set-pin")
async def set_pin(
    data: SetPinRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    return await set_pin_service(db, user.id, data.pin)


# working fine
@router.post("/security/verify-pin")
async def verify_pin(
    data: SetPinRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    return await verify_pin_service(db, user.id, data.pin)


# working fine
@router.put("/security/deactivate-pin")
async def deactivate_user(
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await deactivate_pin_service(db, current_user.id)
