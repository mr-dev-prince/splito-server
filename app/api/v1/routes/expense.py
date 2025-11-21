from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.expense import ExpenseCreate, ExpenseOut
from app.services.expense_services import create_expense, delete_expense, edit_expense
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/")
async def add_expense(data: ExpenseCreate, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await create_expense(db, data, current_user.id)

@router.delete("/{expense_id}")
async def del_expense(expense_id: int, db:AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await delete_expense(db, user_id=current_user.id, expense_id=expense_id)

@router.patch("/{expense_id}")
async def edit(data, expense_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await edit_expense(db, data, expense_id=expense_id, user_id=current_user.id)

# 3 - Expense APIs

#TODO: All expenses in a group

#TODO: Expenses paid by you

#TODO: Expenses you owe

#TODO: Expenses you are owed