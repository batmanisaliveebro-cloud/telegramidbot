
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .models import Base
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase / Postgres requires asyncpg driver
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    # Fallback to local sqlite if no env var
    DB_URL = "sqlite+aiosqlite:///./bot_db.db"

# Ensure async driver is used
if "postgresql" in DB_URL and "asyncpg" not in DB_URL:
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DB_URL, 
    echo=True,
    pool_size=20,          # Increase pool size to handle concurrent requests
    max_overflow=10,       # Allow up to 10 additional connections beyond pool_size
    pool_pre_ping=True,    # Verify connections before using them
    pool_recycle=3600      # Recycle connections every hour to prevent stale connections
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Careful with this
        await conn.run_sync(Base.metadata.create_all)
