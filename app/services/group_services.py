from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, update, func, case, extract, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from app.schemas.group import GroupMemberIn, UpdateGroupName
from app.core.utils import is_group_settled
from app.core.dependencies import ensure_active_group_member, fetch_member_id
from datetime import datetime, timedelta


# working fine
async def create_group(db: AsyncSession, name: str, creator_id: int):
    group = Group(
        name=name,
        created_by=creator_id,
    )
    db.add(group)

    await db.flush()

    user = await db.get(User, creator_id)
    if not user:
        raise ValueError("Creator user not found")

    member = GroupMember(
        group_id=group.id,
        user_id=creator_id,
        name=user.name,
        email=user.email,
        is_admin=True,
    )
    db.add(member)

    await db.commit()
    await db.refresh(group, attribute_names=["members"])

    return group


# working fine
async def delete_group(
    db: AsyncSession,
    group_id: int,
    creator_id: int,
):
    group = await db.scalar(
        select(Group).where(
            Group.id == group_id,
            Group.created_by == creator_id,
            Group.is_deleted == False,
        )
    )

    if not group:
        raise HTTPException(404, "Group doesn't exist")

    if not await is_group_settled(db, group_id):
        raise HTTPException(
            status_code=400,
            detail="Group has unsettled balances. Please settle before deleting.",
        )

    group.is_deleted = True

    await db.execute(
        update(Expense)
        .where(
            Expense.group_id == group_id,
            Expense.is_deleted == False,
        )
        .values(is_deleted=True)
    )

    await db.commit()

    return {"status": "deleted"}


# working fine
async def get_group_by_id(
    db: AsyncSession,
    group_id: int,
    user_id: int,
):
    await ensure_active_group_member(db, user_id, group_id)

    # -----------------------------
    # Current member + admin flag
    # -----------------------------
    res = await db.execute(
        select(GroupMember.id, GroupMember.is_admin).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )

    row = res.first()

    if not row:
        raise HTTPException(400, "User is not a member of the group")

    current_member_id, is_admin = row

    # -----------------------------
    # Total spent in group
    # -----------------------------
    total_spent = (
        await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.group_id == group_id,
                Expense.is_deleted == False,
            )
        )
    ).scalar()

    # -----------------------------
    # My balance (group-scoped)
    # -----------------------------
    my_balance = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Expense.paid_by == current_member_id,
                                Expense.amount - ExpenseSplit.amount,
                            ),
                            else_=-ExpenseSplit.amount,
                        )
                    ),
                    0,
                )
            )
            .select_from(ExpenseSplit)
            .join(Expense, Expense.id == ExpenseSplit.expense_id)
            .where(
                Expense.group_id == group_id,
                Expense.is_deleted == False,
                ExpenseSplit.member_id == current_member_id,
            )
        )
    ).scalar()

    # -----------------------------
    # Member count
    # -----------------------------
    member_count = (
        await db.execute(
            select(func.count(GroupMember.id)).where(GroupMember.group_id == group_id)
        )
    ).scalar()

    # -----------------------------
    # Group
    # -----------------------------
    group = (
        await db.execute(select(Group).where(Group.id == group_id))
    ).scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group doesn't exist")

    # -----------------------------
    # Response
    # -----------------------------
    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "total_spent": float(total_spent),
        "my_balance": float(my_balance),
        "member_count": member_count,
        "is_admin": is_admin,
    }


# working fine
async def add_member(
    db: AsyncSession,
    group_id: int,
    data: GroupMemberIn,
    creator_id: int,
):
    group = await db.scalar(select(Group).where(Group.id == group_id))

    if not group:
        raise HTTPException(404, "Group doesn't exist")

    if group.created_by != creator_id:
        raise HTTPException(403, "Only group admin can add members")

    # Prevent duplicate invite
    exists = await db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            (
                GroupMember.email == data.email
                if data.email
                else GroupMember.phone == data.phone
            ),
        )
    )

    if exists:
        raise HTTPException(400, "Member already exists in group")

    # Try to link user by email
    user_id = None
    if data.email:
        user = await db.scalar(select(User).where(User.email == data.email))
        if user:
            user_id = user.id

    member = GroupMember(
        group_id=group_id,
        name=data.name,
        user_id=user_id,
        email=data.email,
        phone=data.phone,
    )

    db.add(member)
    await db.commit()
    await db.refresh(member)

    return member


# working fine
async def weekly_activity(
    db: AsyncSession,
    group_id: int,
    user_id: int,
):
    member_id = await fetch_member_id(db, user_id, group_id)
    if not member_id:
        raise HTTPException(403, "Not a member of this group")

    today = datetime.utcnow().date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]

    seven_days_ago = today - timedelta(days=6)

    q = (
        select(
            func.date(Expense.created_at).label("day"),
            func.coalesce(func.sum(ExpenseSplit.amount), 0).label("amount"),
        )
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(
            Expense.group_id == group_id,
            Expense.is_deleted == False,
            Expense.created_at >= seven_days_ago,
            ExpenseSplit.member_id == member_id,
        )
        .group_by(func.date(Expense.created_at))
    )

    res = await db.execute(q)

    db_data = {row.day: float(Decimal(str(row.amount))) for row in res.all()}

    # Fill missing days with 0
    daily = []
    for d in days:
        daily.append({"day": d.isoformat(), "amount": db_data.get(d, 0.0)})

    return {"daily": daily}


# working fine
async def list_group_for_user(db: AsyncSession, user_id: int):
    """
    List all groups the user belongs to with:
    - my_balance (per group)
    - member_count
    - is_admin
    """

    member_count_subq = (
        select(
            GroupMember.group_id,
            func.count(GroupMember.id).label("member_count"),
        )
        .group_by(GroupMember.group_id)
        .subquery()
    )

    balance_subq = (
        select(
            Expense.group_id.label("group_id"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Expense.paid_by == GroupMember.id,
                            Expense.amount - ExpenseSplit.amount,
                        ),
                        else_=-ExpenseSplit.amount,
                    )
                ),
                0,
            ).label("my_balance"),
        )
        .select_from(ExpenseSplit)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .join(GroupMember, GroupMember.id == ExpenseSplit.member_id)
        .where(
            GroupMember.user_id == user_id,
            Expense.is_deleted == False,
        )
        .group_by(Expense.group_id)
        .subquery()
    )

    query = (
        select(
            Group,
            GroupMember.is_admin.label("is_admin"),
            func.coalesce(balance_subq.c.my_balance, 0).label("my_balance"),
            func.coalesce(member_count_subq.c.member_count, 0).label("member_count"),
        )
        .join(
            GroupMember,
            (GroupMember.group_id == Group.id) & (GroupMember.user_id == user_id),
        )
        .outerjoin(balance_subq, balance_subq.c.group_id == Group.id)
        .outerjoin(member_count_subq, member_count_subq.c.group_id == Group.id)
        .where(Group.is_deleted == False)
        .order_by(Group.created_at.desc())
    )

    result = await db.execute(query)

    groups = []
    for group, is_admin, my_balance, member_count in result.all():
        groups.append(
            {
                "id": group.id,
                "name": group.name,
                "created_by": group.created_by,
                "created_at": group.created_at,
                "my_balance": float(my_balance),
                "member_count": member_count,
                "is_admin": is_admin,
            }
        )

    return groups


# working fine
async def list_group_members(db: AsyncSession, user_id: int, group_id: int):
    await ensure_active_group_member(db, user_id, group_id)

    q = (
        select(GroupMember, User)
        .outerjoin(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )

    result = await db.execute(q)

    members = []
    for gm, user in result.all():
        members.append(
            {
                "id": gm.id,
                "name": gm.name,
                "email": gm.email or (user.email if user else None),
                "phone": gm.phone,
                "is_admin": gm.is_admin,
                "user_id": gm.user_id,
            }
        )

    return members


# working fine
async def edit_group(
    db: AsyncSession, group_id: int, user_id: int, data: UpdateGroupName
):
    q = select(Group).where(Group.id == group_id)
    res = await db.execute(q)
    group = res.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group doesn't exist")

    if group.created_by != user_id:
        raise HTTPException(403, "Only group admin can edit group")

    if data.name:
        group.name = data.name

    await db.commit()
    await db.refresh(group)
    return {"message": "Group updated successfully"}


# working fine
async def group_analytics_service(db: AsyncSession, user_id: int):
    now = datetime.now()
    first_of_month = datetime(now.year, now.month, 1)

    # 1. Current Month Total (Your Share)
    mtd_stmt = (
        select(func.sum(ExpenseSplit.amount))
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .join(GroupMember, ExpenseSplit.member_id == GroupMember.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Expense.created_at >= first_of_month)
        .filter(Expense.is_deleted == False)
    )
    mtd_total = (await db.execute(mtd_stmt)).scalar() or Decimal("0.00")

    # 2. Lifetime Total
    lifetime_stmt = (
        select(func.sum(ExpenseSplit.amount))
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .join(GroupMember, ExpenseSplit.member_id == GroupMember.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Expense.is_deleted == False)
    )
    lifetime_total = (await db.execute(lifetime_stmt)).scalar() or Decimal("0.00")

    # 3. Average Monthly Expense
    # Count unique months where user had expenses to get a real average
    months_count_stmt = (
        select(
            func.count(
                func.distinct(
                    extract("year", Expense.created_at) * 100
                    + extract("month", Expense.created_at)
                )
            )
        )
        .join(ExpenseSplit, ExpenseSplit.expense_id == Expense.id)
        .join(GroupMember, ExpenseSplit.member_id == GroupMember.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Expense.is_deleted == False)
    )
    total_months = (await db.execute(months_count_stmt)).scalar() or 1
    avg_monthly = lifetime_total / Decimal(total_months)

    # 4. Net Balances (Owed To You vs You Owe)
    # We need: (Sum of expenses PAID by you) - (Sum of your SPLITS)
    # Paid by you
    paid_stmt = (
        select(func.sum(Expense.amount))
        .join(GroupMember, Expense.paid_by == GroupMember.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Expense.is_deleted == False)
    )
    total_paid = (await db.execute(paid_stmt)).scalar() or Decimal("0.00")

    net_balance = total_paid - lifetime_total
    owed_to_you = net_balance if net_balance > 0 else Decimal("0.00")
    you_owe = abs(net_balance) if net_balance < 0 else Decimal("0.00")

    # 5. Total Active Groups
    groups_count_stmt = (
        select(func.count(GroupMember.id))
        .join(Group, GroupMember.group_id == Group.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Group.is_deleted == False)
    )
    active_groups = (await db.execute(groups_count_stmt)).scalar() or 0

    # 6. Top-3 Expense Groups
    top_groups_stmt = (
        select(Group.name, func.sum(ExpenseSplit.amount).label("total"))
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .join(Group, Expense.group_id == Group.id)
        .join(GroupMember, ExpenseSplit.member_id == GroupMember.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Expense.is_deleted == False)
        .group_by(Group.id, Group.name)
        .order_by(desc("total"))
        .limit(3)
    )
    top_groups = [
        {"name": row[0], "amount": float(row[1])}
        for row in (await db.execute(top_groups_stmt)).all()
    ]

    # 7. Top-3 Months
    top_months_stmt = (
        select(
            extract("year", Expense.created_at).label("year"),
            extract("month", Expense.created_at).label("month"),
            func.sum(ExpenseSplit.amount).label("total"),
        )
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .join(GroupMember, ExpenseSplit.member_id == GroupMember.id)
        .filter(GroupMember.user_id == user_id)
        .filter(Expense.is_deleted == False)
        .group_by("year", "month")
        .order_by(desc("total"))
        .limit(3)
    )
    top_months = [
        {
            "period": datetime(int(row[0]), int(row[1]), 1).strftime("%b %Y"),
            "amount": float(row[2]),
        }
        for row in (await db.execute(top_months_stmt)).all()
    ]

    return {
        "mtd_total": float(mtd_total),
        "lifetime_total": float(lifetime_total),
        "avg_monthly_expense": float(avg_monthly),
        "owed_to_you": float(owed_to_you),
        "you_owe": float(you_owe),
        "total_active_groups": active_groups,
        "top_groups": top_groups,
        "top_months": top_months,
    }
