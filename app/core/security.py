from fastapi import HTTPException, Request
from jose import jwt
import httpx

CLERK_ISSUER = "https://valued-earwig-71.clerk.accounts.dev"
CLERK_JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json"
CLERK_AUDIENCE = "your-clerk-frontend-api"

jwks = httpx.get(CLERK_JWKS_URL).json()

def get_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    return auth.split(" ")[1]
 
def verify_clerk_token(request: Request):
    token = get_bearer_token(request)
    unverified_header = jwt.get_unverified_header(token)
    key = next(
        k for k in jwks["keys"]
        if k["kid"] == unverified_header["kid"]
    )

    payload = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=CLERK_AUDIENCE,
        issuer=CLERK_ISSUER,
    )

    return payload