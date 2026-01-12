from fastapi import Depends, HTTPException, Request
from app.schemas.user import AuthUser
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_queries import get_user_by_id
from app.core.security import get_bearer_token, verify_clerk_token
from app.db.session import get_db
from sqlalchemy import select, exists
from app.models.group import Group
from app.models.group_member import GroupMember

async def get_current_user(request: Request,db: AsyncSession = Depends(get_db)) -> AuthUser:
    payload = verify_clerk_token(request)
    clerk_user_id = payload["sub"]

    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )

    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return AuthUser(
        id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        is_active=user.is_active
    )
    
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

async def ensure_user_in_group(
    db: AsyncSession,
    user_id: int,
    group_id: int
):
    q = select(
        exists().where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    result = await db.execute(q)

    if not result.scalar():
        raise HTTPException(status_code=403, detail="Unauthorized access")
