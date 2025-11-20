from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.user import UserCreate, UserOut, UserLogin
from app.models.user import User
from app.services.user_service import create_user, get_user_by_id, get_all_users
from app.core.dependencies import authenticate_user, get_current_user
from app.core.jwt_config import create_access_token, create_refresh_token, decode_token

router = APIRouter()

@router.get("/", response_model=list[UserOut])
async def get_all(db:AsyncSession = Depends(get_db)):
    users = await get_all_users(db)
    return users

@router.post("/register", response_model=UserOut)
async def register_user(data:UserCreate, db:AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/login", response_model=UserOut)
async def login_user(data:UserLogin, response : Response, db:AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.email, data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})

    print(access)

    user.refresh_token = refresh
    await db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=False,
        samesite="none"
    )

    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=False,
        samesite="none"
    )

    return user

@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)

@router.post("/refresh", response_model=UserOut)
async def refresh_token(
    response: Response, 
    db: AsyncSession = Depends(get_db),
    refresh_cookie: str | None = Cookie(None, alias="refresh_token")
):
    if refresh_cookie is None:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        payload = decode_token(refresh_cookie)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    
    user = await get_user_by_id(db, int(user_id))

    if not user:
        raise HTTPException(401, "User not found")
    
    if user.refresh_token != refresh_cookie:
        raise HTTPException(401, "Refresh token revoked or rotated")
    
    new_access = create_access_token({"sub": str(user.id)})

    new_refresh = create_refresh_token({"sub" : str(user.id)})

    await db.commit()
    await db.refresh(user)
    
    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    response.set_cookie(
        "access_token",
        new_access,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    return user

@router.post("/logout")
async def logout_user(response: Response, db: AsyncSession = Depends(get_db), current_user : User = Depends(get_current_user)):
    current_user.refresh_token = None
    await db.commit()

    response.delete_cookie("refresh_token")
    return {"message":"Logged out"}
