from app.core.dependencies import ensure_active_group_member, fetch_member_id
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.group_member import GroupMember
from app.schemas.expense import ExpenseCreate
from app.models.user import User
from app.core.utils import qround
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException


# working fine
async def create_expense(
    db: AsyncSession, data: ExpenseCreate, paid_by: int, group_id: int
):
    # 1. Verify group membership for the payer
    await ensure_active_group_member(db, paid_by, group_id)

    payer_member_id_query = select(GroupMember.id).where(
        GroupMember.group_id == group_id, GroupMember.user_id == paid_by
    )
    res = await db.execute(payer_member_id_query)
    payer_member_id = res.scalar_one_or_none()

    if not payer_member_id:
        raise HTTPException(400, detail="Payer is not a member of the group")

    # 2. Extract & validate unique split users
    member_ids = [s.member_id for s in data.splits]
    if len(member_ids) != len(set(member_ids)):
        raise HTTPException(400, detail="Duplicate users found in splits")

    # -----------------------------------
    # 3. Validate & Reconcile amounts
    # -----------------------------------
    TWOPLACES = Decimal('0.01')
    
    # Standardize the total expense amount
    expense_amount = Decimal(str(data.amount)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    
    # Quantize all split amounts and keep them in a list
    split_amounts = [
        Decimal(str(s.amount)).quantize(TWOPLACES, rounding=ROUND_HALF_UP) 
        for s in data.splits
    ]

    if any(amt <= 0 for amt in split_amounts):
        raise HTTPException(400, detail="Split amounts must be positive")

    # Calculate the "Penny Gap"
    total_split_sum = sum(split_amounts)
    difference = expense_amount - total_split_sum

    # If there's a minor rounding difference (e.g., 0.01 or 0.02), 
    # adjust the first person's split to balance the books.
    if difference != 0:
        # We allow a small threshold for auto-adjustment (e.g., 10 cents)
        # to prevent massive data entry errors from being "auto-fixed"
        if abs(difference) > Decimal('0.10'):
            raise HTTPException(
                400, 
                detail=f"Split total {total_split_sum} differs too much from {expense_amount}"
            )
        split_amounts[0] += difference

    # 4. Validate ALL split users are group members
    members_q = select(GroupMember.id).where(
        GroupMember.group_id == group_id, GroupMember.id.in_(member_ids)
    )
    members_res = await db.execute(members_q)
    valid_member_ids = {row[0] for row in members_res.all()}

    if set(member_ids) != valid_member_ids:
        raise HTTPException(
            400, "One or more users in splits are not members of the group"
        )

    # 5. Create expense record
    expense = Expense(
        group_id=group_id,
        paid_by=payer_member_id,
        amount=expense_amount, # Use the quantized decimal
        title=data.title,
        strategy=data.strategy,
    )

    db.add(expense)
    await db.flush()  # generates expense.id

    # -----------------------------------
    # 6. Create splits using adjusted amounts
    # -----------------------------------
    splits = [
        ExpenseSplit(
            expense_id=expense.id, 
            member_id=data.splits[i].member_id, 
            amount=split_amounts[i] # Use the reconciled amount
        )
        for i in range(len(data.splits))
    ]

    db.add_all(splits)

    await db.commit()
    await db.refresh(expense)

    return expense

# working fine
async def delete_expense(db: AsyncSession, user_id: int, expense_id: int):
    # Fetch expense
    q = select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False)
    res = await db.execute(q)
    expense = res.scalar_one_or_none()

    member_id = await fetch_member_id(db, user_id, expense.group_id)

    if not expense:
        raise HTTPException(404, detail="Expense not found")

    # Authorization: only payer can delete
    if expense.paid_by != member_id:
        raise HTTPException(403, detail="You cannot delete this expense")

    # Cascade deletes ExpenseSplit if relationship is set
    expense.is_deleted = True
    await db.commit()

    return {"status": "deleted"}


# working fine
async def get_my_expenses(db: AsyncSession, user_id: int):
    my_member = aliased(GroupMember)
    payer_member = aliased(GroupMember)
    payer_user = aliased(User)

    q = (
        select(
            Expense.id,
            Expense.group_id,
            Expense.title,
            Expense.amount,
            Expense.created_at,
            Expense.strategy,
            Expense.paid_by,
            ExpenseSplit.amount.label("my_share"),
            payer_user.name.label("payer_name"),
        )
        .select_from(ExpenseSplit)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .join(my_member, my_member.id == ExpenseSplit.member_id)
        .join(payer_member, payer_member.id == Expense.paid_by)
        .join(payer_user, payer_user.id == payer_member.user_id)
        .where(
            my_member.user_id == user_id,
            Expense.is_deleted == False,
        )
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )

    res = await db.execute(q)

    return [
        {
            "id": row.id,
            "group_id": row.group_id,
            "title": row.title,
            "amount": float(row.amount),
            "paid_by": row.paid_by,
            "payer_name": row.payer_name,
            "strategy": row.strategy,
            "created_at": row.created_at,
            "my_share": float(row.my_share),
        }
        for row in res.all()
    ]


# working fine
async def get_expenses(db: AsyncSession, user_id: int):
    q = (
        select(Expense)
        .outerjoin(ExpenseSplit, Expense.id == ExpenseSplit.expense_id)
        .where((Expense.paid_by == user_id) | (ExpenseSplit.user_id == user_id))
        .order_by(Expense.created_at.desc(), Expense.id.desc())
        .distinct()
    )

    res = await db.execute(q)
    return res.scalars().all()


# working fine
async def get_expenses_by_group(
    db: AsyncSession,
    group_id: int,
    user_id: int,
):
    await ensure_active_group_member(db, user_id, group_id)

    current_member_id = await fetch_member_id(db, user_id, group_id)

    if not current_member_id:
        raise HTTPException(400, "User is not a member of the group")

    my_split = aliased(ExpenseSplit)
    payer_member = aliased(GroupMember)
    payer_user = aliased(User)

    q = (
        select(
            Expense,
            func.coalesce(func.sum(my_split.amount), 0).label("my_share"),
            payer_user.name.label("payer_name"),
        )
        # join to get my share
        .outerjoin(
            my_split,
            (my_split.expense_id == Expense.id)
            & (my_split.member_id == current_member_id),
        )
        # join to get payer name
        .join(
            payer_member,
            payer_member.id == Expense.paid_by,
        )
        .join(
            payer_user,
            payer_user.id == payer_member.user_id,
        )
        .where(
            Expense.group_id == group_id,
            Expense.is_deleted == False,
        )
        .group_by(
            Expense.id,
            payer_user.name,
        )
        .order_by(
            Expense.created_at.desc(),
            Expense.id.desc(),
        )
    )

    res = await db.execute(q)
    rows = res.all()

    return [
        {
            "id": expense.id,
            "group_id": expense.group_id,
            "title": expense.title,
            "amount": float(expense.amount),
            "paid_by": expense.paid_by,
            "payer_name": payer_name,
            "strategy": expense.strategy,
            "created_at": expense.created_at,
            "my_share": float(my_share),
        }
        for expense, my_share, payer_name in rows
    ]
