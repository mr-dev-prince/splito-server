from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from collections import defaultdict
from decimal import Decimal
from sqlalchemy.orm import selectinload
from typing import Dict
from app.core.utils import simplify_debts


# working fine
async def admin_group_settlements(db: AsyncSession, user_id: int):
    # 1. Fetch all groups where this user is an admin
    # We load members, expenses, and splits in one go to avoid N+1 issues
    admin_groups_query = (
        select(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .filter(GroupMember.user_id == user_id, GroupMember.is_admin == True)
        .filter(Group.is_deleted == False)
        .options(
            selectinload(Group.members),
            selectinload(Group.members).selectinload(
                GroupMember.group
            ),  # To keep relations warm
            selectinload(Group.members)
            .selectinload(GroupMember.group)
            .selectinload(Group.members),
        )
    )

    result = await db.execute(admin_groups_query)
    groups = result.scalars().all()

    response_data = []

    for group in groups:
        # We need to calculate net balance for every member in THIS group
        # net_balance = (Total amount paid by member) - (Total share of expenses for member)
        member_balances: Dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
        member_names: Dict[int, str] = {m.id: m.name for m in group.members}

        # Fetch all expenses for this group
        expenses_query = (
            select(Expense)
            .filter(Expense.group_id == group.id, Expense.is_deleted == False)
            .options(selectinload(Expense.splits))
        )
        exp_result = await db.execute(expenses_query)
        expenses = exp_result.scalars().all()

        for exp in expenses:
            # Payer gets credit
            member_balances[exp.paid_by] += Decimal(str(exp.amount))

            # Splitters get debited
            for split in exp.splits:
                member_balances[split.member_id] -= Decimal(str(split.amount))

        # Simplify the debts for this specific group
        transfers = simplify_debts(member_balances)

        # Format the output for the UI
        group_settlements = []
        for debt_id, cred_id, amt in transfers:
            group_settlements.append(
                {
                    "from_member_id": debt_id,
                    "from_member_name": member_names.get(debt_id, "Unknown"),
                    "to_member_id": cred_id,
                    "to_member_name": member_names.get(cred_id, "Unknown"),
                    "amount": float(amt),
                }
            )

        response_data.append(
            {
                "group_id": group.id,
                "group_name": group.name,
                "total_members": len(group.members),
                "settlements": group_settlements,
            }
        )

    return response_data
