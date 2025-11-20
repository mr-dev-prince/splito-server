from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.group_services import create_group, add_member, list_group_for_user
from app.schemas.group import GroupCreate, GroupMemberOut, GroupOut
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=GroupOut)
async def create_new_group(
    data:GroupCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    group = await create_group(db, data.name, user.id)
    return group

@router.post("/{group_id}/add/{user_id}", response_model=GroupMemberOut)
async def add_user_to_group(group_id: int, user_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await add_member(db, group_id, user_id)

@router.get("/my-groups", response_model=list[GroupOut])
async def my_groups(db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    return await list_group_for_user(db, user.id)