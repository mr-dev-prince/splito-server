from pydantic import BaseModel
from datetime import datetime

class Settlement(BaseModel):
    from_user: int
    to_user: int
    amount: float

class SettlementHistoryCreate(BaseModel):
    group_id: int
    to_user: int
    amount: float

class SettlementHistoryOut(BaseModel):
    id: int
    group_id: int
    from_user: int
    to_user: int
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True