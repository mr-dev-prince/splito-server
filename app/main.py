from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.routes.system import router as system_router
from app.api.v1.routes.user import router as user_router
from app.api.v1.routes.group import router as group_router
from app.api.v1.routes.expense import router as expense_router
from app.api.v1.routes.balances import router as balance_router
from app.api.v1.routes.webhook import router as webhook_router

app = FastAPI(title="Splitwise Backend")

origins = (
    [settings.CLIENT_URL]
    if settings.ENV == "production"
    else ["http://localhost:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.head("/")
async def head_root():
    return {}

@app.get("/") 
async def root():
    return {"message": "Splitwise Backend is live"}

app.include_router(system_router, prefix="/api/v1/system")
app.include_router(user_router, prefix="/api/v1/users") 
app.include_router(group_router, prefix="/api/v1/groups")
app.include_router(expense_router, prefix="/api/v1/expenses")
app.include_router(balance_router, prefix="/api/v1/balances")
app.include_router(webhook_router, prefix="/api/v1/webhooks")