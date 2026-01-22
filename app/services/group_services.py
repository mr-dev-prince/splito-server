from decimal import Decimal
from typing import Dict
from fastapi import HTTPException
from sqlalchemy import select, update, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from app.schemas.group import GroupMemberIn, UpdateGroupName
from app.core.utils import qround, simplify_debts, is_group_settled
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
    # Fetch group (must exist and not already deleted)
    group = await db.scalar(
        select(Group).where(
            Group.id == group_id,
            Group.created_by == creator_id,
            Group.is_deleted == False,
        )
    )

    if not group:
        raise HTTPException(404, "Group doesn't exist")

    # Check settlement
    if not await is_group_settled(db, group_id):
        raise HTTPException(
            status_code=400,
            detail="Group has unsettled balances. Please settle before deleting."
        )

    # Soft-delete group
    group.is_deleted = True

    # Soft-delete all expenses in this group
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
            select(func.count(GroupMember.id)).where(
                GroupMember.group_id == group_id
            )
        )
    ).scalar()

    # -----------------------------
    # Group
    # -----------------------------
    group = (
        await db.execute(
            select(Group).where(Group.id == group_id)
        )
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
    group = await db.scalar(
        select(Group).where(Group.id == group_id)
    )

    if not group:
        raise HTTPException(404, "Group doesn't exist")

    if group.created_by != creator_id:
        raise HTTPException(403, "Only group admin can add members")

    # Prevent duplicate invite
    exists = await db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.email == data.email
            if data.email else
            GroupMember.phone == data.phone
        )
    )

    if exists:
        raise HTTPException(400, "Member already exists in group")

    # Try to link user by email
    user_id = None
    if data.email:
        user = await db.scalar(
            select(User).where(User.email == data.email)
        )
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

    db_data = {
        row.day: float(Decimal(str(row.amount)))
        for row in res.all()
    }

    # Fill missing days with 0
    daily = []
    for d in days:
        daily.append({
            "day": d.isoformat(),
            "amount": db_data.get(d, 0.0)
        })

    return {"daily": daily}

async def remove_member(db: AsyncSession, group_id: int, user_id: int, creator_id: int):
    #TODO: if balance due, restrict removal of member
    res1 = await db.execute(select(Group).where(Group.id == group_id))
    group = res1.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group does not exist")

    if group.created_by != creator_id:
        raise HTTPException(403, "Only group admin can remove members")

    if user_id == creator_id:
        raise HTTPException(400, "Transfer admin role before removing yourself")

    res = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(404, "User is not a member of this group")

    await db.delete(member)
    await db.commit()

    return {"status": "member_removed"}

async def exit_group(db: AsyncSession, group_id: int, user_id: int):
    #TODO : if balance is due, restrict user to exit
    res = await db.execute(select(Group).where(Group.id == group_id))
    group = res.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group not found")

    if group.create_by == user_id:
        raise HTTPException(400, "Group admin cannot exit. Transfer admin role first.")

    res_mem = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    member = res_mem.scalar_one_or_none()

    if not member:
        raise HTTPException(404, "You are not a member of this group")

    await db.delete(member)
    await db.commit()

    return {"status": "exited_group"}

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
            (GroupMember.group_id == Group.id)
            & (GroupMember.user_id == user_id),
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

async def list_group_members(db:AsyncSession, user_id:int, group_id: int):
    await ensure_active_group_member(db, user_id, group_id)

    q = (
        select(GroupMember, User)
        .outerjoin(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )

    result = await db.execute(q)

    members = []
    for gm, user in result.all():
        members.append({
            "id": gm.id,
            "name": gm.name,
            "email": gm.email or (user.email if user else None),
            "phone": gm.phone,
            "is_admin": gm.is_admin,
            "user_id": gm.user_id,
        })

    return members

async def edit_group(db: AsyncSession, group_id: int, user_id: int, data: UpdateGroupName):
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

async def get_group_net_balances(db : AsyncSession, group_id: int) -> Dict[int, Decimal]:
    paid_q = (
        select(Expense.paid_by, func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.group_id == group_id)
        .group_by(Expense.paid_by)
    )

    paid_res = await db.execute(paid_q)
    paid_rows = paid_res.all()

    owed_q = (
        select(ExpenseSplit.user_id, func.coalesce(func.sum(ExpenseSplit.amount), 0))
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.group_id == group_id)
        .group_by(ExpenseSplit.user_id)
    )

    owed_res = await db.execute(owed_q)
    owed_rows = owed_res.all()

    paid_map: Dict[int, Decimal] = {row[0]: Decimal(str(row[1])) for row in paid_rows}
    owed_map: Dict[int, Decimal] = {row[0]: Decimal(str(row[1])) for row in owed_rows}

    user_ids = set(paid_map.keys()) | set(owed_map.keys())

    net: Dict[int, Decimal] = {}
    for uid in user_ids:
        p = paid_map.get(uid, Decimal("0"))
        o = owed_map.get(uid, Decimal("0"))
        net[uid] = qround(p-o)

    return net

async def get_group_settlement_plan(db: AsyncSession, group_id: int):
    net = await get_group_net_balances(db, group_id=group_id)

    net = {uid: (qround(amount)) if abs(amount) >= Decimal("0.005") else Decimal("0") for uid, amount in net.items()}

    net = {uid: amt for uid, amt in net.items() if amt != 0}

    transfers = simplify_debts(net)

    if transfers:
        user_ids = set()

        for f, t, _ in transfers:
            user_ids.add(f); user_ids.add(t)
        q = select(User.id, User.name).where(User.id.in_(list(user_ids)))
        res = await db.execute(q)
        users = {row[0]: row[1] for row in res.all()}

        plan = [
            {
                "from_id": f, "from_name": users.get(f),
                "to_id": t, "to_name": users.get(t),
                "amount": float(a)
            }
            for f, t, a in transfers
        ]
    else:
        plan = []

    return {"net": {uid: float(amount) for uid, amount in net.items()}, "settlements": plan}

async def list_group_expenses(
        db: AsyncSession,
        user_id: int,
        group_id: int
):
    check_q = (
        select(GroupMember)
        .where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )

    check = await db.execute(check_q)

    if not check.scalar():
        raise HTTPException(status_code=403, detail="Unauthorized Access")
    

    expense_q = (
        select(
            Expense,
            User.id.label("payer_id"),
            User.name.label("payer_name")
        )
        .join(User, User.id == Expense.paid_by)
        .where(
            Expense.group_id == group_id,
            # Expense.is_deleted == False
        )
        .order_by(Expense.created_at, Expense.id)
    )

    expense_res = await db.execute(expense_q)
    expense_rows = expense_res.all()

    if not expense_res:
        return []
    
    expense_ids =[row.Expense.id for row in expense_rows]

    splits_q = (
        select(
            ExpenseSplit.expense_id,
            ExpenseSplit.user_id,
            ExpenseSplit.amount
        )
        .where(ExpenseSplit.expense_id.in_(expense_ids))
    )

    splits_res = await db.execute(splits_q)
    split_rows = splits_res.all()

    splits_map = {}

    for expense_id, user_id, amount in split_rows:
        splits_map.setdefault(expense_id, []).append({
            "user_id" : user_id,
            "amount": str(qround(Decimal(str(amount))))
        })
    
    result = []
    for row in expense_rows:
        expense = row.Expense
        result.append({
            "id": expense.id,
            "description": expense.description,
            "amount": str(qround(Decimal(str(expense.amount)))),
            "created_at": expense.created_at,
            "paid_by": {
                "id": row.payer_id,
                "name": row.payer_name
            },
            "splits": splits_map.get(expense.id, [])
        })
    
    return result

# 10 - Services