from pydantic import BaseModel, condecimal
from typing import List, Literal

class SplitInput(BaseModel):
    member_id: int
    amount: float

class ExpenseCreate(BaseModel):
    title: str
    amount: int
    strategy: Literal["equal", "percentage", "exact"]
    splits: List[SplitInput]

class ExpenseOut(BaseModel):
    id: int
    group_id: int
    amount: float
    description: str | None = None
    paid_by: int
    splits : List[SplitInput]

    class Config:
        from_attributes = True
