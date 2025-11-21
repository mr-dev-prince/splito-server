from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.core.jwt_config import decode_token, get_token_from_cookie
from app.services.user_service import get_user_by_id, get_user_by_email
from app.core.security import verify_password
from sqlalchemy import select
from app.models.group import Group
from app.models.group_member import GroupMember

async def get_db():
    async with async_session() as session:
        yield session

async def get_current_user(request: Request,db: AsyncSession = Depends(get_db)):
    try:
        token = get_token_from_cookie(request=request)
        payload = decode_token(token)
        print(payload)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        user = await get_user_by_id(db, int(user_id))

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
async def authenticate_user(db:AsyncSession, email:str, password:str):
    user = await get_user_by_email(db, email)
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user

async def check_group_membership(db: AsyncSession, group_id: int, user_id: int):
    q_group = select(Group).where(Group.id == group_id)
    res_group = await db.execute(q_group)
    group = res_group.scalar_one_or_none()

    if not group:
        raise HTTPException(404, "Group does not exist")

    q_member = select(GroupMember).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    )

    res_member = await db.execute(q_member)
    member = res_member.scalar_one_or_none()

    if not member:
        raise HTTPException(403, "You are not a member of this group")

    return member