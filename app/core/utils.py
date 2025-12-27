from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from collections import deque

getcontext().prec = 28
CENTS= Decimal("0.01")

def qround(d : Decimal) -> Decimal:
    return d.quantize(CENTS, rounding=ROUND_HALF_UP)

def simplify_debts(net_map: Dict[int, Decimal]):
    creditors = []
    debtors = []

    for uid, bal in net_map.items():
        if bal > 0:
            creditors.append([uid, bal])
        elif bal < 0:
            debtors.append([uid, -bal])
    

    creditors.sort(key= lambda x: x[1], reverse=True)
    debtors.sort(key= lambda x: x[1], reverse=True)

    creditors = deque(creditors)
    debtors = deque(debtors)

    transfers : List[Tuple[int, int, Decimal]] = []

    while creditors and debtors:
        cred_id, cred_amt = creditors[0]
        debt_id, debt_amt = debtors[0]

        pay_amt = qround(min(cred_amt, debt_amt))

        transfers.append((debt_id, cred_id, pay_amt))

        new_cred = qround(cred_amt - pay_amt)
        new_debt = qround(debt_amt - pay_amt)

        creditors.popleft()
        debtors.popleft()

        if new_cred > Decimal("0"):
            creditors.appendleft([cred_id, new_cred])
        if new_debt > Decimal("0"):
            debtors.appendleft([debt_id, new_debt])
    return transfers

async def get_user_total_balance(db: AsyncSession, user_id: int):
    paid_q = select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.paid_by == user_id)
    paid_res = await db.execute(paid_q)
    paid = Decimal(str(paid_res.scalar() or 0))

    owed_q = (
        select(func.coalesce(func.sum(ExpenseSplit.amount), 0))
        .where(ExpenseSplit.user_id == user_id)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
    )

    owed_res = await db.execute(owed_q)
    owed = Decimal(str(owed_res.scalar() or 0))
    
    return qround(paid - owed)

async def get_overall_net_map(db: AsyncSession) -> Dict[int, Decimal]:
    paid_q = (
        select(
            Expense.paid_by,
            func.coalesce(func.sum(Expense.amount), 0)
        )
        .where(Expense.is_deleted == False)
        .group_by(Expense.paid_by)
    )
    paid_res = await db.execute(paid_q)
    paid_map = {
        uid: qround(Decimal(str(amt)))
        for uid, amt in paid_res.all()
    }

    owed_q = (
        select(
            ExpenseSplit.user_id,
            func.coalesce(func.sum(ExpenseSplit.amount), 0)
        )
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.is_deleted == False)
        .group_by(ExpenseSplit.user_id)
    )
    owed_res = await db.execute(owed_q)
    owed_map = {
        uid: qround(Decimal(str(amt)))
        for uid, amt in owed_res.all()
    }

    user_ids = set(paid_map) | set(owed_map)

    net = {}
    for uid in user_ids:
        net[uid] = qround(
            paid_map.get(uid, Decimal("0")) -
            owed_map.get(uid, Decimal("0"))
        )

    return net
