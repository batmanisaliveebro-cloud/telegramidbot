"""
Clear Phone Numbers (Accounts) from Database
This will DELETE ONLY ACCOUNTS TABLE data, keeping users, countries, deposits, etc.
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Get database URL from environment
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    print("❌ DATABASE_URL not found in environment variables!")
    exit(1)

# Ensure async driver
if "postgresql" in DB_URL and "asyncpg" not in DB_URL:
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://")

async def clear_accounts():
    """Delete all accounts (phone numbers) from database"""
    
    engine = create_async_engine(DB_URL, echo=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    print("\n" + "="*60)
    print("⚠️  CLEARING PHONE NUMBERS (ACCOUNTS TABLE)")
    print("="*60 + "\n")
    
    async with async_session() as session:
        try:
            # First delete purchases that reference accounts
            print("🗑️  Deleting purchases (references accounts)...")
            await session.execute(text("DELETE FROM purchases"))
            
            # Then delete accounts
            print("🗑️  Deleting all accounts (phone numbers)...")
            result = await session.execute(text("DELETE FROM accounts"))
            
            # Commit the transaction
            await session.commit()
            
            print("\n" + "="*60)
            print("✅ ACCOUNTS CLEARED!")
            print("="*60)
            print(f"\nAll phone numbers deleted.")
            print("Users, countries, deposits, and settings remain intact.\n")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error during clear: {e}")
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    print("\n⚠️  WARNING: This will DELETE ALL PHONE NUMBERS (accounts)!")
    print("Users, countries, and other data will remain.\n")
    
    confirm = input("Type 'CLEAR' to confirm: ")
    
    if confirm == "CLEAR":
        asyncio.run(clear_accounts())
    else:
        print("\n❌ Clear cancelled. Database unchanged.")
