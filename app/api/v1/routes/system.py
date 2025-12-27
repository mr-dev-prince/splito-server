from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.system_services import check_db_service, system_metrics, system_health
from app.db.session import get_db

router = APIRouter()

@router.get("/health/db")
async def check_db():
    return await check_db_service()

@router.get("/metrics")
async def metrics(
    db: AsyncSession = Depends(get_db)
):
    return await system_metrics(db)

@router.get("/health")
async def health():
    return await system_health()
