"""
Safe Database Clear Script
Clears all user data but preserves:
- Database schema
- Countries list (60+ countries we just added)
- Settings (payment UPI, etc.)

Clears:
- Users
- Purchases
- Deposits
- Accounts (phone numbers)
"""
import asyncio
from backend.database import async_session
from backend.models import User, Purchase, Deposit, Account
from sqlalchemy import delete


async def safe_clear_database():
    """Safely clear user data while keeping countries and settings"""
    
    print("\n" + "="*60)
    print("SAFE DATABASE CLEAR")
    print("="*60)
    print("\n⚠️  This will DELETE:")
    print("   - All users")
    print("   - All purchases")
    print("   - All deposits")
    print("   - All accounts (phone numbers)")
    print("\n✅ This will KEEP:")
    print("   - All countries (60+ countries)")
    print("   - All settings (UPI ID, etc.)")
    print("   - Database schema")
    print("\n" + "="*60)
    
    confirm = input("\nType 'CLEAR' to proceed: ")
    
    if confirm != "CLEAR":
        print("❌ Cancelled. No changes made.")
        return
    
    async with async_session() as session:
        # Count before deletion
        purchases_count = len((await session.execute("SELECT * FROM purchases")).fetchall())
        deposits_count = len((await session.execute("SELECT * FROM deposits")).fetchall())
        accounts_count = len((await session.execute("SELECT * FROM accounts")).fetchall())
        users_count = len((await session.execute("SELECT * FROM users")).fetchall())
        
        print(f"\n📊 Current data:")
        print(f"   Purchases: {purchases_count}")
        print(f"   Deposits: {deposits_count}")
        print(f"   Accounts: {accounts_count}")
        print(f"   Users: {users_count}")
        
        print("\n🗑️  Deleting data...")
        
        # Delete in correct order (foreign keys)
        await session.execute(delete(Purchase))
        print("   ✅ Purchases cleared")
        
        await session.execute(delete(Deposit))
        print("   ✅ Deposits cleared")
        
        await session.execute(delete(Account))
        print("   ✅ Accounts cleared")
        
        await session.execute(delete(User))
        print("   ✅ Users cleared")
        
        await session.commit()
        
        # Verify countries and settings still exist
        countries_count = len((await session.execute("SELECT * FROM countries")).fetchall())
        settings_count = len((await session.execute("SELECT * FROM settings")).fetchall())
        
        print(f"\n✅ Database cleared successfully!")
        print(f"\n📊 Preserved data:")
        print(f"   Countries: {countries_count} (intact)")
        print(f"   Settings: {settings_count} (intact)")
        print("\n💡 Bot is safe to run. All features will work.")
        print("   Users can register fresh, purchase accounts normally.")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(safe_clear_database())
