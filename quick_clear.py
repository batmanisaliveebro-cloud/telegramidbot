import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if "postgresql" in DB_URL and "asyncpg" not in DB_URL:
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://")

async def clear():
    engine = create_async_engine(DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as s:
        print("Deleting purchases...")
        await s.execute(text('DELETE FROM purchases'))
        print("Deleting accounts...")
        await s.execute(text('DELETE FROM accounts'))
        await s.commit()
        print('✅ All accounts (phone numbers) cleared!')
    
    await engine.dispose()

asyncio.run(clear())
