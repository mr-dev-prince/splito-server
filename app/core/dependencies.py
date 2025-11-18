from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.core.jwt_config import decode_token
from app.services.user_service import get_user_by_id, get_user_by_email
from app.core.security import verify_password
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer("/api/v1/users/login") 

async def get_db():
    async with async_session() as session:
        yield session

async def get_current_user(db: AsyncSession = Depends(get_db), 
                           token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        user = await get_user_by_id(db, int(user_id))

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
async def authenticate_user(db:AsyncSession, email:str, password:str):
    user = await get_user_by_email(db, email)
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user