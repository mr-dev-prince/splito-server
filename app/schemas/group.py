from pydantic import BaseModel
from typing import List

class GroupCreate(BaseModel):
    name: str

class GroupOut(BaseModel):
    id: int
    name: str
    created_by: int

    class Config:
        from_attributes = True
        
class GroupMemberOut(BaseModel):
    user_id: int
    group_id: int

    class Config:
        from_attributes = True