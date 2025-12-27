from app.db.session import engine
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.group import Group
from app.models.expense import Expense

async def check_db_service():
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return {"db": True, "message":"Database is connected"}
    except Exception as e:
        return {"db": False, "error": str(e)}
    
async def system_health():
    return {
        "status": "ok"
    }

async def system_metrics(db: AsyncSession):
    users_q = select(func.count(User.id))
    groups_q = select(func.count(Group.id))
    expenses_q = select(func.count(Expense.id)).where(
        Expense.is_deleted == False
    )

    users_res = await db.execute(users_q)
    groups_res = await db.execute(groups_q)
    expenses_res = await db.execute(expenses_q)

    return {
        "users": users_res.scalar(),
        "groups": groups_res.scalar(),
        "expenses": expenses_res.scalar()
    }