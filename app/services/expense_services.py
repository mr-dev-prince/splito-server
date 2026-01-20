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
from decimal import Decimal
from fastapi import HTTPException

# TODO : store upi_id with user data and generate qr code for payments

# working fine
async def create_expense(db: AsyncSession, data: ExpenseCreate, paid_by: int, group_id: int):
    await ensure_active_group_member(db, paid_by, group_id)

    payer_member_id = select(GroupMember.id).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == paid_by
    )

    res = await db.execute(payer_member_id)

    payer_member_id = res.scalar_one_or_none()

    if not payer_member_id:
        raise HTTPException(400, "Payer is not a member of the group")
    
    # -----------------------------------
    # 2. Extract & validate split users
    # -----------------------------------
    member_ids = [s.member_id for s in data.splits]

    if len(member_ids) != len(set(member_ids)):
        raise HTTPException(400, "Duplicate users found in splits")

    # -----------------------------------
    # 3. Validate amounts
    # -----------------------------------
    if any(Decimal(s.amount) <= 0 for s in data.splits):
        raise HTTPException(400, "Split amounts must be positive")

    total_split = sum(Decimal(s.amount) for s in data.splits)
    if total_split != Decimal(data.amount):
        raise HTTPException(
            400,
            f"Split total ({total_split}) must equal expense amount ({data.amount})"
        )

    # -----------------------------------
    # 4. Validate ALL split users are group members
    # -----------------------------------
    members_q = select(GroupMember.id).where(
        GroupMember.group_id == group_id,
        GroupMember.id.in_(member_ids)
    )

    members_res = await db.execute(members_q)

    valid_user_ids = {row[0] for row in members_res.all()}

    if set(member_ids) != valid_user_ids:
        raise HTTPException(
            400,
            "One or more users in splits are not members of the group"
        )

    # -----------------------------------
    # 5. Create expense
    # -----------------------------------
    expense = Expense(
        group_id=group_id,
        paid_by=payer_member_id,
        amount=data.amount,
        title=data.title,
        strategy=data.strategy
    )

    db.add(expense)
    await db.flush()  # generates expense.id

    # -----------------------------------
    # 6. Create splits
    # -----------------------------------
    splits = [
        ExpenseSplit(
            expense_id=expense.id,
            member_id=s.member_id,
            amount=s.amount
        )
        for s in data.splits
    ]

    db.add_all(splits)

    await db.commit()
    await db.refresh(expense)

    return expense

async def delete_expense(db: AsyncSession, user_id: int, expense_id: int):
    # Fetch expense
    q = select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False)
    res = await db.execute(q)
    expense = res.scalar_one_or_none()

    if not expense:
        raise HTTPException(404, "Expense not found")

    # Authorization: only payer can delete
    if expense.paid_by != user_id:
        raise HTTPException(403, "You cannot delete this expense")

    # Cascade deletes ExpenseSplit if relationship is set
    expense.is_deleted = True
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

async def get_my_expenses(
    db: AsyncSession,
    user_id: int
):
    q = (
        select(Expense)
        .where(Expense.paid_by == user_id)
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )

    res = await db.execute(q)
    return res.scalars().all()

async def get_debt(
    db: AsyncSession,
    user_id: int
):
    q = (
        select(
            Expense.id.label("expense_id"),
            Expense.description,
            Expense.group_id,
            Expense.created_at,
            Expense.paid_by,
            ExpenseSplit.amount.label("owed_amount"),
            User.name.label("payer_name")
        )
        .join(ExpenseSplit, Expense.id == ExpenseSplit.expense_id)
        .join(User, User.id == Expense.paid_by)
        .where(
            ExpenseSplit.user_id == user_id,
            ExpenseSplit.amount > 0,
            Expense.paid_by != user_id,
            # Expense.is_deleted == False
        )
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )

    res = await db.execute(q)
    rows = res.all()

    total = Decimal("0")
    expenses = []

    for row in rows:
        amt = qround(Decimal(str(row.owed_amount)))
        total += amt

        expenses.append({
            "expense_id": row.expense_id,
            "description": row.description,
            "group_id": row.group_id,
            "paid_by": {
                "id": row.paid_by,
                "name": row.payer_name
            },
            "amount_i_owe": str(amt),
            "created_at": row.created_at
        })

    return {
        "total_debt": str(qround(total)),
        "expenses": expenses
    }

async def get_cred(
    db: AsyncSession,
    user_id: int
):
    q = (
        select(
            Expense.id.label("expense_id"),
            Expense.description,
            Expense.group_id,
            Expense.created_at,
            ExpenseSplit.user_id.label("debtor_id"),
            ExpenseSplit.amount.label("owed_amount"),
            User.name.label("debtor_name")
        )
        .join(ExpenseSplit, Expense.id == ExpenseSplit.expense_id)
        .join(User, User.id == ExpenseSplit.user_id)
        .where(
            Expense.paid_by == user_id,
            ExpenseSplit.user_id != user_id,
            ExpenseSplit.amount > 0,
            # Expense.is_deleted == False
        )
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )

    res = await db.execute(q)
    rows = res.all()

    total = Decimal("0")
    credits = []

    for row in rows:
        amt = qround(Decimal(str(row.owed_amount)))
        total += amt

        credits.append({
            "expense_id": row.expense_id,
            "description": row.description,
            "group_id": row.group_id,
            "owed_by": {
                "id": row.debtor_id,
                "name": row.debtor_name
            },
            "amount_owed": str(amt),
            "created_at": row.created_at
        })

    return {
        "total_credit": str(qround(total)),
        "credits": credits
    }

async def get_expenses(
    db: AsyncSession,
    user_id: int
):
    q = (
        select(Expense)
        .outerjoin(ExpenseSplit, Expense.id == ExpenseSplit.expense_id)
        .where(
            (Expense.paid_by == user_id) |
            (ExpenseSplit.user_id == user_id)
        )
        .order_by(Expense.created_at.desc(), Expense.id.desc())
        .distinct()
    )

    res = await db.execute(q)
    return res.scalars().all()

async def get_expense_by_id(
    db: AsyncSession,
    expense_id: int,
    user_id: int
):
    q = (
        select(
            Expense,
            User.id.label("payer_id"),
            User.name.label("payer_name")
        )
        .join(User, User.id == Expense.paid_by)
        .where(
            Expense.id == expense_id,
            Expense.is_deleted == False
        )
    )

    res = await db.execute(q)
    row = res.first()

    if not row:
        raise HTTPException(404, "Expense not found")

    expense = row.Expense

    q_member = (
        select(GroupMember)
        .where(
            GroupMember.group_id == expense.group_id,
            GroupMember.user_id == user_id
        )
    )

    member_res = await db.execute(q_member)
    if not member_res.scalar_one_or_none():
        raise HTTPException(403, "Unauthorized access")

    splits_q = (
        select(
            ExpenseSplit.user_id,
            ExpenseSplit.amount
        )
        .where(ExpenseSplit.expense_id == expense_id)
        .order_by(ExpenseSplit.user_id)
    )

    splits_res = await db.execute(splits_q)
    split_rows = splits_res.all()

    splits = [
        {
            "user_id": uid,
            "amount": str(qround(Decimal(str(amount))))
        }
        for uid, amount in split_rows
    ]

    return {
        "id": expense.id,
        "description": expense.description,
        "amount": str(qround(Decimal(str(expense.amount)))),
        "created_at": expense.created_at,
        "paid_by": {
            "id": row.payer_id,
            "name": row.payer_name
        },
        "splits": splits
    }

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
