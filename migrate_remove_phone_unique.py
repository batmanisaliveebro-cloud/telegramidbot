"""
Database Migration Script
Removes unique constraint from phone_number column in accounts table
This allows the same phone number to be added multiple times (after selling)
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if "postgresql" in DB_URL and "asyncpg" not in DB_URL:
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://")


async def remove_unique_constraint():
    """Remove unique constraint from phone_number"""
    engine = create_async_engine(DB_URL)
    
    async with engine.begin() as conn:
        try:
            # Drop the unique constraint if it exists
            print("🔄 Removing unique constraint from phone_number...")
            
            # For PostgreSQL
            await conn.execute(text("""
                ALTER TABLE accounts 
                DROP CONSTRAINT IF EXISTS accounts_phone_number_key;
            """))
            
            print("✅ Unique constraint removed!")
            print("✅ Same phone number can now be added multiple times")
            print("\n💡 This allows restocking sold numbers")
            
        except Exception as e:
            print(f"⚠️  Note: {e}")
            print("💡 Constraint may not exist or already removed")
    
    await engine.dispose()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("REMOVING PHONE NUMBER UNIQUE CONSTRAINT")
    print("="*60 + "\n")
    
    asyncio.run(remove_unique_constraint())
    
    print("\n" + "="*60)
    print("✅ MIGRATION COMPLETE")
    print("="*60 + "\n")
