from fastapi import HTTPException, Request
from app.core.security import verify_clerk_token

def clerk_auth(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth.split(" ")[1]

    try:
        payload = verify_clerk_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "clerk_user_id": payload["sub"],
        "email": payload.get("email"),
    }
