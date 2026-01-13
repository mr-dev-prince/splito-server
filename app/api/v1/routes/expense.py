from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.expense import ExpenseCreate
from app.services.expense_services import create_expense, delete_expense, edit_expense, get_my_expenses, get_debt, get_cred, get_expenses, get_expense_by_id, get_expenses_by_group
from app.core.dependencies import get_current_user

router = APIRouter()

# working fine
@router.post("/{group_id}/add")
async def add_expense(group_id: int, data: ExpenseCreate, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    print("Received data:", data)
    return await create_expense(db, data, current_user.id, group_id)

# working fine
@router.get("/{group_id}/all")
async def all_expenses(group_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await get_expenses_by_group(db, group_id, current_user.id)

@router.delete("/{expense_id}")
async def del_expense(expense_id: int, db:AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await delete_expense(db, user_id=current_user.id, expense_id=expense_id)

@router.patch("/{expense_id}")
async def edit(data, expense_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await edit_expense(db, data, expense_id=expense_id, user_id=current_user.id)

@router.get("/my-expenses")
async def expenses_paid_by_me(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await get_my_expenses(db, user_id=current_user.id)

@router.get("/debt")
async def expenses_i_owe(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await get_debt(db, user_id=current_user.id)

@router.get("/cred")
async def expenses_i_am_owed(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await get_cred(db, user_id=current_user.id)

@router.get("/my-expenses/all")
async def my_expenses(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await get_expenses(db, user_id=current_user.id)

@router.get("/{expense_id}")
async def fetch(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await get_expense_by_id(
        db,
        expense_id=expense_id,
        user_id=current_user.id
    )

