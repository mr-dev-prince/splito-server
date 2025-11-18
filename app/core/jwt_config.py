import jwt
from jwt import PyJWKError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from fastapi import HTTPException

def create_access_token(data: dict, expires_min: int = 30):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_min)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm = settings.JWT_ALGO)


def create_refresh_token(data: dict, expires_days: int = 7):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    to_encode.update({"exp" : expire})

    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm = settings.JWT_ALGO)

def decode_token(token : str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms = [settings.JWT_ALGO]
        )

        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except PyJWKError:
        raise HTTPException(status_code=401, detail="Invalid Token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))