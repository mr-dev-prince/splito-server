from fastapi import APIRouter, Depends
from app.schemas.user import AuthUser
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.group_services import (
    create_group,
    add_member,
    list_group_for_user,
    list_group_members,
    delete_group,
    edit_group,
    get_group_by_id,
    weekly_activity,
    group_analytics_service,
)
from app.schemas.group import (
    GroupCreate,
    CreateGroupResponse,
    GroupDetailOut,
    GroupListResponse,
    GroupMemberIn,
    UpdateGroupName,
    UpdateGroupResponse,
)
from app.core.dependencies import get_current_user


router = APIRouter()


# working fine
@router.post("/", response_model=CreateGroupResponse, description="create new group")
async def create_new_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    group = await create_group(db, data.name, user.id)
    return CreateGroupResponse(id=group.id)


# working fine
@router.get("/", response_model=list[GroupListResponse], description="get user groups")
async def get_groups(
    db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)
):
    return await list_group_for_user(db, user.id)


# working fine
@router.get("/analytics")
async def fetch_analytics(
    db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)
):
    return await group_analytics_service(db, user.id)


# working fine
@router.get("/{group_id}", response_model=GroupDetailOut, description="get group by id")
async def get_group_data(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await get_group_by_id(db, group_id, current_user.id)


# working fine
@router.patch(
    "/{group_id}", response_model=UpdateGroupResponse, description="edit group details"
)
async def edit(
    group_id: int,
    data: UpdateGroupName,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await edit_group(db, group_id, current_user.id, data)


# working fine
@router.delete("/{group_id}")
async def del_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    return await delete_group(db, group_id, user.id)


# working fine
@router.post("/{group_id}/members")
async def add_group_member(
    group_id: int,
    data: GroupMemberIn,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await add_member(db, group_id, data, current_user.id)


# working fine
@router.get("/{group_id}/weekly-activity")
async def get_weekly_activity(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await weekly_activity(db, group_id, current_user.id)


# working fine
@router.get("/{group_id}/members")
async def group_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await list_group_members(db, current_user.id, group_id)
