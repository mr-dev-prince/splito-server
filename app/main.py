from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes.system import router as system_router
from app.api.v1.routes.user import router as user_router
from app.api.v1.routes.group import router as group_router
from app.api.v1.routes.expense import router as expense_router
from app.api.v1.routes.balances import router as balance_router
from app.api.v1.routes.webhook import router as webhook_router

app = FastAPI(title="Splitwise Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Splitwise Backend is live"}

app.include_router(system_router, prefix="/api/v1/system")
app.include_router(user_router, prefix="/api/v1/users") 
app.include_router(group_router, prefix="/api/v1/groups")
app.include_router(expense_router, prefix="/api/v1/expense")
app.include_router(balance_router, prefix="/api/v1/balances")
app.include_router(webhook_router, prefix="/api/v1/webhooks")
