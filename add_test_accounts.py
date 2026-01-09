"""
Quick script to add test accounts to database for testing bot
"""
import asyncio
from backend.database import async_session
from backend.models import Account, Country
from sqlalchemy import select

async def add_test_accounts():
    """Add 5 test accounts for each country"""
    async with async_session() as session:
        # Get all countries
        stmt = select(Country)
        result = await session.execute(stmt)
        countries = result.scalars().all()
        
        if not countries:
            print("❌ No countries found! Run seed_world_countries.py first!")
            return
        
        added = 0
        for country in countries[:10]:  # Add accounts for first 10 countries
            for i in range(1, 6):  # 5 accounts per country
                account = Account(
                    country_id=country.id,
                    phone_number=f"+{country.id}123456{i:04d}",  # Fake number
                    type="ID",
                    session_data=f"test_session_string_{country.id}_{i}",
                    is_sold=False
                )
                session.add(account)
                added += 1
        
        await session.commit()
        print(f"✅ Added {added} test accounts across {min(10, len(countries))} countries!")
        print(f"💡 Bot should now show countries when you click 'Get Account'")

if __name__ == "__main__":
    print("🔧 Adding Test Accounts...\n")
    asyncio.run(add_test_accounts())
