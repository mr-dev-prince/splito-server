from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.expense import ExpenseCreate
from app.services.expense_services import (
    create_expense,
    delete_expense,
    get_my_expenses,
    get_expenses_by_group,
)
from app.core.dependencies import get_current_user

router = APIRouter()


# working fine
@router.post("/{group_id}/add")
async def add_expense(
    group_id: int,
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await create_expense(db, data, current_user.id, group_id)


# working fine
@router.get("/{group_id}/all")
async def all_expenses(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await get_expenses_by_group(db, group_id, current_user.id)


# working fine
@router.delete("/{expense_id}")
async def del_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await delete_expense(db, user_id=current_user.id, expense_id=expense_id)


# working fine
@router.get("/my-expenses")
async def expenses_paid_by_me(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    print(user.id)
    return await get_my_expenses(db, user_id=user.id)
