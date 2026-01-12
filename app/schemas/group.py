from pydantic import BaseModel, model_validator

class GroupCreate(BaseModel):
    name: str

class GroupOut(BaseModel):
    id: int
    name: str
    created_by: int

    class Config:
        from_attributes = True
        
class GroupMemberOut(BaseModel):
    name:str
    email: str | None = None
    phone: str | None = None
    user_id: int | None = None
    group_id: int

    class Config:
        from_attributes = True

class GroupMemberIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def validate_input(self):
        if not self.name:
            return ValueError("Name is required")
        if not self.email and not self.phone:
            raise ValueError("Email or phone is required")
        return self
