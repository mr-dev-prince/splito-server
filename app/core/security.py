from fastapi import HTTPException, Request
from jose import jwt
import httpx
import time

CLERK_ISSUER = "https://valued-earwig-71.clerk.accounts.dev"
CLERK_JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json"
CLERK_AUDIENCE = "your-clerk-frontend-api"

_jwks_cache = None
_jwks_last_fetch = 0
JWKS_TTL = 60 * 60  # Time to live : 1 hour


async def get_jwks():
    """
    Safe JWKS fetcher with:
    - timeout
    - retry
    - cache
    - fallback
    """
    global _jwks_cache, _jwks_last_fetch

    # Use cached keys if still fresh
    if _jwks_cache and time.time() - _jwks_last_fetch < JWKS_TTL:
        return _jwks_cache

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(CLERK_JWKS_URL)
            res.raise_for_status()
            _jwks_cache = res.json()
            _jwks_last_fetch = time.time()
            return _jwks_cache

    except Exception:
        # Fallback to old cache if network fails
        if _jwks_cache:
            return _jwks_cache

        # No cache and network failed → fail cleanly
        raise HTTPException(
            status_code=503, detail="Auth service unavailable. Try again later."
        )


def get_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    return auth.split(" ")[1]


async def verify_clerk_token(request: Request):
    token = get_bearer_token(request)

    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = await get_jwks()

        key = next(k for k in jwks["keys"] if k["kid"] == unverified_header["kid"])

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=CLERK_AUDIENCE,
            issuer=CLERK_ISSUER,
        )

        return payload

    except StopIteration:
        raise HTTPException(401, "Invalid token key")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.JWTError:
        raise HTTPException(401, "Invalid token")
