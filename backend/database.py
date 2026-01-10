```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
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

# CRITICAL: Increased pool size and added recycling for bot + admin panel stability
# This prevents connection exhaustion when both bot and admin panel are active
engine = create_async_engine(
    DB_URL, 
    echo=True,
    pool_size=40,          # Increased to 40 to handle bot + admin panel concurrently
    max_overflow=20,       # Allow up to 20 additional connections (60 total)
    pool_pre_ping=True,    # Verify connections before using them
    pool_recycle=3600,     # Recycle connections every hour to prevent stale connections
    pool_timeout=15        # Increased timeout to 15 seconds for high load scenarios
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Careful with this
        await conn.run_sync(Base.metadata.create_all)
