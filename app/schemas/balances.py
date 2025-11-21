from pydantic import BaseModel

class NetBalance(BaseModel):
    user_id: int
    amount: float

class Settlement(BaseModel):
    from_id: int
    from_name: str | None
    to_id: int
    to_name: str | None
    amount: float

class GroupBalanceOut(BaseModel):
    net: dict[int, float] 
    settlements: list[Settlement]
