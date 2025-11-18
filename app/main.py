from fastapi import FastAPI
from app.api.v1.routes.system import router as system_router
from app.api.v1.routes.user import router as user_router

app = FastAPI(title="Splitwise Backend")

@app.get("/")
async def root():
    return {"message": "Splitwise Backend is live"}

app.include_router(system_router, prefix="/api/v1/system")
app.include_router(user_router, prefix="/api/v1/users")