from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.group_member import GroupMember
from app.schemas.settlements import Settlement
from fastapi import HTTPException
from app.models.settlement_history import SettlementHistory

async def compute_group_settlements(db: AsyncSession, group_id: int, user_id: int):
    # Ensure user is in group
    q = select(GroupMember).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    )
    is_member = await db.scalar(q)
    if not is_member:
        raise HTTPException(403, "You are not a member of this group")

    # Step 1: Fetch all expenses of group
    q_exp = select(Expense).where(Expense.group_id == group_id)
    expenses = (await db.scalars(q_exp)).all()

    # Step 2: Calculate balances per user
    balances = {}  # user_id → balance

    for exp in expenses:
        # paid_by increases balance
        balances[exp.paid_by] = balances.get(exp.paid_by, 0) + float(exp.amount)

        # splits decrease balance
        q_split = select(ExpenseSplit).where(ExpenseSplit.expense_id == exp.id)
        splits = (await db.scalars(q_split)).all()

        for s in splits:
            balances[s.user_id] = balances.get(s.user_id, 0) - float(s.amount)

    # Step 3: Convert balances into payers/receivers
    payers = []     # (user_id, amount_owed)
    receivers = []  # (user_id, amount_to_receive)

    for uid, bal in balances.items():
        if bal < 0:
            payers.append([uid, -bal])  # store as positive amount to pay
        elif bal > 0:
            receivers.append([uid, bal])

    # Step 4: Greedy settlement matching
    settlements = []
    i = 0
    j = 0

    while i < len(payers) and j < len(receivers):
        payer_id, owe = payers[i]
        receiver_id, recv = receivers[j]

        amount = min(owe, recv)

        settlements.append(Settlement(
            from_user=payer_id,
            to_user=receiver_id,
            amount=amount
        ))

        payers[i][1] -= amount
        receivers[j][1] -= amount

        if payers[i][1] == 0:
            i += 1
        if receivers[j][1] == 0:
            j += 1

    return settlements

async def add_settlement(db: AsyncSession, user_id: int, data):
    # User must be part of group
    q = select(GroupMember).where(
        GroupMember.group_id == data.group_id,
        GroupMember.user_id == user_id
    )
    if not await db.scalar(q):
        raise HTTPException(403, "You are not a member of this group")

    # to_user must also be part of group
    q2 = select(GroupMember).where(
        GroupMember.group_id == data.group_id,
        GroupMember.user_id == data.to_user
    )
    if not await db.scalar(q2):
        raise HTTPException(400, "Receiver is not in this group")

    settlement = SettlementHistory(
        group_id=data.group_id,
        from_user=user_id,
        to_user=data.to_user,
        amount=data.amount
    )

    db.add(settlement)
    await db.commit()
    await db.refresh(settlement)

    return settlement

async def get_settlement_history(db: AsyncSession, group_id: int, user_id: int):
    # Ensure requester is in group
    q = select(GroupMember).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    )
    if not await db.scalar(q):
        raise HTTPException(403, "You are not a member of this group")

    # Fetch history
    q2 = select(SettlementHistory).where(
        SettlementHistory.group_id == group_id
    ).order_by(SettlementHistory.created_at.desc())

    result = await db.execute(q2)
    return result.scalars().all()

async def undo_settlement(db: AsyncSession, settlement_id: int, user_id: int):
    # Fetch settlement
    q = select(SettlementHistory).where(SettlementHistory.id == settlement_id)
    result = await db.execute(q)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(404, "Settlement entry not found")
    
    # Only the user who made the payment can undo it
    if settlement.from_user != user_id:
        raise HTTPException(403, "You are not allowed to undo this settlement")

    # Ensure user is still in group
    q2 = select(GroupMember).where(
        GroupMember.group_id == settlement.group_id,
        GroupMember.user_id == user_id
    )

    if not await db.scalar(q2):
        raise HTTPException(403, "You are not a member of this group")

    # Delete the record
    await db.delete(settlement)
    await db.commit()

    return { "status": "undo successful" }

#TODO: remove membership check for user - add at route through util function
