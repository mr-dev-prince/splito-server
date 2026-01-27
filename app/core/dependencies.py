from fastapi import Depends, HTTPException, Request
from app.schemas.user import AuthUser
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_clerk_token
from app.db.session import get_db
from sqlalchemy import select, exists
from app.models.group import Group
from app.models.group_member import GroupMember


# working fine
async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> AuthUser:
    payload = await verify_clerk_token(request)
    clerk_user_id = payload["sub"]

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))

    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return AuthUser(
        id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        is_active=user.is_active,
    )


# working fine
async def ensure_active_group_member(
    db: AsyncSession,
    user_id: int,
    group_id: int,
):
    # Check group exists and is not deleted
    group = await db.scalar(
        select(Group.id).where(
            Group.id == group_id,
            Group.is_deleted == False,
        )
    )

    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found or has been deleted",
        )

    # Check membership
    is_member = await db.scalar(
        select(
            exists().where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
        )
    )

    if not is_member:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized access",
        )


# working fine
async def fetch_member_id(db: AsyncSession, user_id: int, group_id: int):
    q = select(GroupMember.id).where(
        GroupMember.user_id == user_id, GroupMember.group_id == group_id
    )
    result = await db.execute(q)
    member_id = result.scalar_one_or_none()

    if not member_id:
        raise HTTPException(status_code=404, detail="Membership not found")

    return member_id
