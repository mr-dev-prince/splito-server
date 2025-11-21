from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from decimal import Decimal
from typing import Dict
from fastapi import HTTPException
from sqlalchemy import func
from app.core.utils import qround, simplify_debts

async def create_group(db: AsyncSession, name:str, creator_id:int):
    group = Group(name=name, created_by=creator_id)
    db.add(group)
    await db.flush()

    member = GroupMember(group_id=group.id, user_id=creator_id)
    db.add(member)

    await db.commit()
    await db.refresh(group)
    return group

async def delete_group(db: AsyncSession, group_id: int, creator_id: int):
    q = select(Group).where(Group.id == group_id, Group.created_by == creator_id)
    res = await db.execute(q)
    group = res.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group doesn't exist")
    
    await db.delete(group)
    await db.commit()

    return {"status": "deleted"}

async def add_member(db: AsyncSession, group_id: int, user_id: int, creator_id: int):
    q = select(Group).where(Group.id == group_id)
    res = await db.execute(q)
    group = res.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group doesn't exist")
    
    if group.created_by != creator_id:
        raise HTTPException(403, "Only the group creator can add members")
    
    check_q = select(GroupMember).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    )

    existing = await db.execute(check_q)
    member = existing.scalar_one_or_none()

    if member:
        raise HTTPException(400, "User already exist in this group")

    new_member = GroupMember(group_id=group_id, user_id=user_id)
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)
    return new_member

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

async def list_group_for_user(db: AsyncSession, user_id: int):
    q = (
        select(Group)
        .join(GroupMember)
        .where(GroupMember.user_id == user_id)
    )
    result = await db.execute(q)
    return result.scalars().all()

async def list_group_members(db:AsyncSession, user_id:int, group_id: int):
    check_q = (
        select(GroupMember)
        .where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )

    check = await db.execute(check_q)

    if not check.scalar():
        raise HTTPException(status_code=403, detail="Unauthorized access")
    
    members__q = (
        select(User)
        .join(GroupMember, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )

    result = await db.execute(members__q)
    users = result.scalars().all()
    return users

async def edit_group(db: AsyncSession, group_id: int, user_id: int, data):
    q = select(Group).where(Group.id == group_id)
    res = await db.execute(q)
    group = res.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group doesn't exist")
    
    if group.created_by != user_id:
        raise HTTPException(403, "Only group admin can edit group")
    
    if data.name:
        group.name = data.name

    #TODO: add group descriptions

    await db.commit()
    await db.refresh(group)
    return group

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


# 10 - Services