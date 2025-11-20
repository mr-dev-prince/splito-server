from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.group import Group
from app.models.group_member import GroupMember

async def create_group(db: AsyncSession, name:str, creator_id:int):
    group = Group(name=name, created_by=creator_id)
    db.add(group)
    await db.flush()

    member = GroupMember(group_id=group.id, user_id=creator_id)
    db.add(member)

    await db.commit()
    await db.refresh(group)
    return group

async def add_member(db: AsyncSession, group_id: int, user_id: int):
    member = GroupMember(group_id=group_id, user_id=user_id)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member

async def list_group_for_user(db: AsyncSession, user_id: int):
    q = (
        select(Group)
        .join(GroupMember)
        .where(GroupMember.user_id == user_id)
    )
    result = await db.execute(q)
    return result.scalars().all()