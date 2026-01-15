from fastapi import APIRouter, Depends
from app.schemas.user import AuthUser
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.group_services import create_group, add_member, list_group_for_user, list_group_members, delete_group, remove_member, exit_group, edit_group, get_group_settlement_plan, list_group_expenses, get_group_by_id
from app.schemas.group import GroupCreate,CreateGroupResponse, GroupDetailOut, GroupMemberOut, GroupListResponse, GroupMemberIn
from app.schemas.balances import GroupBalanceOut
from app.core.dependencies import get_current_user, check_group_membership
from app.services.settlement_service import compute_group_settlements, add_settlement, get_settlement_history,undo_settlement
from app.schemas.settlements import Settlement, SettlementHistoryCreate, SettlementHistoryOut

router = APIRouter()

# working fine
@router.post("/", response_model=CreateGroupResponse, description="create new group")
async def create_new_group(
    data:GroupCreate,
    db: AsyncSession = Depends(get_db),
    user : AuthUser = Depends(get_current_user)
):
   group = await create_group(db, data.name, user.id)
   return CreateGroupResponse(id=group.id)

# working fine
@router.get("/", response_model=list[GroupListResponse], description="get user groups")
async def get_groups(db: AsyncSession = Depends(get_db), user : AuthUser = Depends(get_current_user)):
    return await list_group_for_user(db, user.id)

# working fine
@router.get("/{group_id}", response_model=GroupDetailOut, description="get group by id")
async def get_group_data(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return await get_group_by_id(db, group_id, current_user.id)
    
# @router.patch("/{group_id}")
# async def edit(group_id: int, data, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
#     await check_group_membership(db, group_id, current_user.id)
#     return await edit_group(db, group_id, current_user.id, data)

@router.delete("/{group_id}")
async def del_group(group_id: int, db: AsyncSession = Depends(get_db), current_user: int = Depends(get_current_user)):
    return await delete_group(db, group_id=group_id, creator_id=current_user.id)

# working fine
@router.post("/{group_id}/members") 
async def add_group_member(
    group_id: int,
    data: GroupMemberIn,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return await add_member(db, group_id, data, current_user.id)

# @router.delete("/{group_id}/remove/{user_id}")
# async def rem_mem(group_id: int, user_id : int, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
#     await check_group_membership(db, group_id, current_user.id)
#     return await remove_member(db, group_id=group_id, user_id=user_id, creator_id = current_user.id)

# @router.delete("/{group_id}/exit")
# async def exit(group_id: int, db:AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
#     await check_group_membership(db, group_id, current_user.id)
#     return await exit_group(db, group_id=group_id, user_id=current_user.id)

# working fine
@router.get("/{group_id}/members")
async def group_members(group_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    await check_group_membership(db, group_id, current_user.id)
    return await list_group_members(db, current_user.id, group_id=group_id)

# @router.get("/{group_id}/balances", response_model=GroupBalanceOut)
# async def group_balances(group_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
#     await check_group_membership(db, group_id, current_user.id)
#     plan = await get_group_settlement_plan(db, group_id=group_id)
#     return plan

# @router.get("/{group_id}/settlements", response_model=list[Settlement])
# async def get_group_settlements(
#     group_id: int,
#     db: AsyncSession = Depends(get_db),
#     user = Depends(get_current_user)
# ):
#     return await compute_group_settlements(db, group_id, user.id)

# @router.post("/{group_id}/settlements/add", response_model=SettlementHistoryOut)
# async def add_manual_settlement(
#     data: SettlementHistoryCreate,
#     db: AsyncSession = Depends(get_db),
#     user = Depends(get_current_user)
# ):
#     return await add_settlement(db, user.id, data)

# @router.delete("/{group_id}/settlements/undo/{settlement_id}")
# async def undo_settlement_route(
#     settlement_id: int,
#     db: AsyncSession = Depends(get_db),
#     user = Depends(get_current_user)
# ):
#     return await undo_settlement(db, settlement_id, user.id)

# @router.get("/{group_id}/settlement-history", response_model=list[SettlementHistoryOut])
# async def fetch_history(
#     group_id: int,
#     db: AsyncSession = Depends(get_db),
#     user = Depends(get_current_user)
# ):
#     return await get_settlement_history(db, group_id, user.id)

# @router.get("/{group_id}/expenses", description="get all expenses of the group")
# async def fetch_expenses(
#     group_id: int,
#     db: AsyncSession = Depends(get_db),
#     user = Depends(get_current_user)
# ):
#     return await list_group_expenses(db, user.id, group_id)

# 13 - Group APIs