from fastapi import APIRouter
from app.db.session import engine

router = APIRouter()

@router.get("/health/db")
async def check_db():
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return {"db": True, "message":"Database is connected"}
    except Exception as e:
        return {"db": False, "error": str(e)}
