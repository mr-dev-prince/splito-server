from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.group_member import GroupMember
from fastapi import HTTPException

async def create_expense(db: AsyncSession, data, paid_by: int):
    # 1. Check if payer is member of group
    q = select(GroupMember).where(
        GroupMember.group_id == data.group_id,
        GroupMember.user_id == paid_by
    )
    result = await db.execute(q)
    
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Payer is not a member of the group")

    # Extract user_ids from split input
    user_ids = [s.user_id for s in data.splits]

    # 2. Check duplicates
    if len(user_ids) != len(set(user_ids)):
        raise HTTPException(400, "Duplicate users found in splits")

    # 3. Validate positive amount
    if any(s.amount <= 0 for s in data.splits):
        raise HTTPException(400, "Split amounts must be positive")

    # 4. Validate sum of splits == total
    total = sum(s.amount for s in data.splits)
    if total != data.amount:
        raise HTTPException(400, "Sum of split amounts must equal total amount")

    # 5. Validate all users in split are members of the group
    q2 = select(GroupMember).where(
        GroupMember.group_id == data.group_id,
        GroupMember.user_id.in_(user_ids)
    )
    result2 = await db.execute(q2)
    members = result2.scalars().all()

    if len(members) != len(user_ids):
        raise HTTPException(400, "Some users in split are not group members")

    # 6. Create expense
    expense = Expense(
        group_id=data.group_id,
        paid_by=paid_by,
        amount=data.amount,
        description=data.description
    )
    db.add(expense)
    await db.flush()  # gives expense.id

    # 7. Create split records
    for s in data.splits:
        split = ExpenseSplit(
            expense_id=expense.id,
            user_id=s.user_id,
            amount=s.amount
        )
        db.add(split)

    await db.commit()
    await db.refresh(expense)

    return expense

async def delete_expense(db: AsyncSession, user_id: int, expense_id: int):
    # Fetch expense
    q = select(Expense).where(Expense.id == expense_id)
    res = await db.execute(q)
    expense = res.scalar_one_or_none()

    if not expense:
        raise HTTPException(404, "Expense not found")

    # Authorization: only payer can delete
    if expense.paid_by != user_id:
        raise HTTPException(403, "You cannot delete this expense")

    # Cascade deletes ExpenseSplit if relationship is set
    await db.delete(expense)
    await db.commit()

    return {"status": "deleted"}

async def edit_expense(db: AsyncSession, data, expense_id: int, user_id: int):
    q = select(Expense).where(Expense.id == expense_id)
    res = await db.execute(q)
    expense = res.scalar_one_or_none()

    if not expense:
        raise HTTPException(404, "Expense doesn't exist")
    
    if expense.paid_by != user_id:
        raise HTTPException(403, "You can't edit this expense")
    
    q_member = select(GroupMember).where(
        GroupMember.group_id == expense.group_id,
        GroupMember.user_id == user_id
    )

    member = await db.execute(q_member)

    if not member.scalar_one_or_none():
        raise HTTPException(403, "You are not member of this group")
    
    user_ids = [s.user_id for s in data.splits]

    if len(user_ids) >= len(set(user_ids)):
        raise HTTPException(400, "Duplicate users in split") 
    
    total = sum(s.amout for s in data.splits)

    if total != data.amount:
        raise HTTPException(400, "Split sums do not match the amount")
    
    q_members = select(GroupMember).where(
        GroupMember.group_id == expense.group_id,
        GroupMember.user_id.in_(user_ids)
    )

    rows = await db.execute(q_members)

    if len(rows.scalars().all()) != len(user_ids):
        raise HTTPException(400, "Some users are not group members")
    
    expense.amount = data.amount
    expense.description = data.description

    del_q = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)
    old_splits = await db.execute(del_q)

    for s in old_splits.scalars().all():
        await db.delete(s)

    for s in data.splits:
        new_s = ExpenseSplit(
            expense_id=expense_id,
            user_id=s.user_id,
            amount=s.amount
        )
        db.add(new_s)

    await db.commit()
    await db.refresh(expense)
    return expense

# 3 - Expense