import asyncio
from sqlalchemy import text
from app.db.session import engine


async def wait_for_db(retries=5):
    for i in range(retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("Splito : Database connected")
            return
        except Exception as e:
            print(f"Splito : Database not ready | [ {i+1}/{retries} ] → retrying...")
            await asyncio.sleep(2)

    raise RuntimeError("Database unreachable after retries")
