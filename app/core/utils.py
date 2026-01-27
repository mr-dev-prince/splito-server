from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from collections import deque

getcontext().prec = 28
CENTS = Decimal("0.01")


def qround(d: Decimal) -> Decimal:
    return d.quantize(CENTS, rounding=ROUND_HALF_UP)


# working fine
def simplify_debts(net_map: Dict[int, Decimal]):
    """
    Standard Greedy algorithm to minimize number of transactions.
    """
    creditors = []
    debtors = []

    for uid, bal in net_map.items():
        if bal > Decimal("0.01"):  # Avoid floating point noise
            creditors.append([uid, bal])
        elif bal < Decimal("-0.01"):
            debtors.append([uid, -bal])

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    creditors = deque(creditors)
    debtors = deque(debtors)

    transfers: List[Tuple[int, int, Decimal]] = []

    while creditors and debtors:
        cred_id, cred_amt = creditors[0]
        debt_id, debt_amt = debtors[0]

        pay_amt = qround(min(cred_amt, debt_amt))

        if pay_amt > 0:
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


# working fine
async def get_group_net_balances(
    db: AsyncSession,
    group_id: int,
) -> Dict[int, Decimal]:
    """
    Returns:
        {
            member_id: net_balance (Decimal)
        }

    net_balance = total_paid - total_owed
    """

    # Total paid by each member
    paid_q = (
        select(
            Expense.paid_by.label("member_id"),
            func.coalesce(func.sum(Expense.amount), 0).label("paid"),
        )
        .where(Expense.group_id == group_id, Expense.is_deleted == False)
        .group_by(Expense.paid_by)
    )

    paid_res = await db.execute(paid_q)
    paid_map = {row.member_id: Decimal(str(row.paid)) for row in paid_res}

    # Total owed by each member
    owed_q = (
        select(
            ExpenseSplit.member_id,
            func.coalesce(func.sum(ExpenseSplit.amount), 0).label("owed"),
        )
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.group_id == group_id, Expense.is_deleted == False)
        .group_by(ExpenseSplit.member_id)
    )

    owed_res = await db.execute(owed_q)
    owed_map = {row.member_id: Decimal(str(row.owed)) for row in owed_res}

    # Union of all members involved
    member_ids = set(paid_map.keys()) | set(owed_map.keys())

    net: Dict[int, Decimal] = {}
    for member_id in member_ids:
        net[member_id] = paid_map.get(member_id, Decimal("0")) - owed_map.get(
            member_id, Decimal("0")
        )

    return net


# working fine
async def is_group_settled(
    db: AsyncSession,
    group_id: int,
    tolerance: Decimal = Decimal("0.05"),
) -> bool:
    """
    A group is settled if:
        abs(net_balance) <= tolerance
        for every member
    """

    net_balances = await get_group_net_balances(db, group_id)

    for amount in net_balances.values():
        if abs(amount) > tolerance:
            return False

    return True
