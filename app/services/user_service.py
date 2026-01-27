import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User
from datetime import datetime, timezone
from sqlalchemy import update
from fastapi import HTTPException, status


def check_pin(plain_pin: str, hashed_pin: str) -> bool:
    """
    Checks if the plain PIN matches the stored bcrypt hash.
    """
    try:
        return bcrypt.checkpw(plain_pin.encode("utf-8"), hashed_pin.encode("utf-8"))
    except Exception:
        return False


def hash_pin(pin: str) -> str:
    """
    Hashes a 4-digit PIN using bcrypt.
    Note: bcrypt requires bytes, so we encode/decode.
    """
    # 1. Convert string PIN to bytes
    byte_pin = pin.encode("utf-8")

    # 2. Generate a salt and hash the password
    # 12 rounds is a good balance between security and speed
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(byte_pin, salt)

    # 3. Return as a string for database storage
    return hashed.decode("utf-8")


async def create_user_from_clerk(db, data: dict) -> User:
    clerk_user_id = data["id"]

    primary_email_id = data.get("primary_email_address_id")
    email = None
    for e in data.get("email_addresses", []):
        if e["id"] == primary_email_id:
            email = e["email_address"]
            break

    if not email:
        raise ValueError("Primary email not found")

    first = data.get("first_name") or ""
    last = data.get("last_name") or ""
    name = f"{first} {last}".strip() or "Splito User"
    avatar_url = data.get("image_url")

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if user:
        if not user.is_active or user.deleted_at:
            user.is_active = True
            user.deleted_at = None

        user.email = email
        user.name = name
        user.avatar_url = avatar_url

        await db.commit()
        await db.refresh(user)
        return user

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        user.clerk_user_id = clerk_user_id
        user.is_active = True
        user.deleted_at = None
        user.name = name
        user.avatar_url = avatar_url

        await db.commit()
        await db.refresh(user)
        return user

    user = User(
        clerk_user_id=clerk_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def update_user_from_clerk(db: AsyncSession, data: dict):
    clerk_user_id = data["id"]

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if not user:
        return None  # user not created yet

    email_addresses = data.get("email_addresses", [])
    if email_addresses:
        user.email = email_addresses[0]["email_address"]

    first_name = data.get("first_name") or ""
    last_name = data.get("last_name") or ""
    user.name = f"{first_name} {last_name}".strip() or user.name

    user.avatar_url = data.get("image_url")

    await db.commit()
    await db.refresh(user)

    return user


async def deactivate_user_from_clerk(
    db: AsyncSession,
    data: dict,
):
    clerk_user_id = data.get("id")
    if not clerk_user_id:
        return None

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if not user:
        # webhook may arrive for a user you never stored
        return None

    # Idempotent: safe to run multiple times
    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)

    return user


async def set_pin_service(db: AsyncSession, user_id: int, plain_pin: str):
    # Validation
    if not plain_pin or len(plain_pin) != 4 or not plain_pin.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIN must be exactly 4 digits.",
        )

    # Secure Hashing
    try:
        hashed_pin = hash_pin(plain_pin)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing security credentials.",
        )

    # Database Update
    stmt = (
        update(User)
        .where(User.id == user_id)
        .where(User.is_active == True)
        .values(security_pin=hashed_pin, security_pin_active=True)
    )

    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or account is inactive.",
        )

    await db.commit()
    return {"message": "Security PIN set successfully", "status": "success"}


async def verify_pin_service(db: AsyncSession, user_id: int, plain_pin: str):
    # Fetch the hashed pin from the DB
    query = select(User.security_pin).where(User.id == user_id)
    result = await db.execute(query)
    stored_hash = result.scalar_one_or_none()

    if not stored_hash:
        raise HTTPException(status_code=404, detail="PIN not set for this user.")

    if not check_pin(plain_pin, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid security PIN.")

    return {"message": "PIN verified", "status": "success"}


async def deactivate_pin_service(db: AsyncSession, user_id: int):
    """
    Service to deactivate (remove) a user's security PIN.
    """
    stmt = (
        update(User)
        .where(User.id == user_id)
        .where(User.is_active == True)
        .values(security_pin=None, security_pin_active=False)
    )

    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive."
        )

    await db.commit()

    return {"message": "Security PIN deactivated successfully", "status": "success"}


async def get_user_data(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    user.security_pin = None 
    return user
