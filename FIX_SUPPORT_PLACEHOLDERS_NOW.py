"""
EMERGENCY FIX - REMOVE PLACEHOLDER VALUES FROM DATABASE RIGHT NOW!
This will DELETE the bad @YourChannel values immediately
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_support_now():
    from backend.database import async_session
    from backend.models import Settings
    from sqlalchemy import select, delete
    
    print("\n" + "="*70)
    print("🚨 EMERGENCY FIX - REMOVING PLACEHOLDER VALUES")
    print("="*70)
    
    async with async_session() as session:
        # DELETE the bad placeholder values
        from sqlalchemy import delete
        
        # Delete bot_channel_link if it has placeholder
        stmt = select(Settings).where(Settings.key == "bot_channel_link")
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            print(f"\nFound channel_link: {setting.value}")
            if "yourchannel" in setting.value.lower() or setting.value == "https://t.me/akhilportal":
                await session.delete(setting)
                print("❌ DELETED placeholder channel_link!")
            else:
                print(f"✅ Channel link looks good: {setting.value}")
        else:
            print("⚠️ No channel_link found in database")
        
        # Delete bot_owner_username if it has placeholder
        stmt = select(Settings).where(Settings.key == "bot_owner_username")
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            print(f"\nFound owner_username: {setting.value}")
            if "yourchannel" in setting.value.lower() or "akhilportal" in setting.value.lower() or setting.value == "@akhilportal":
                await session.delete(setting)
                print("❌ DELETED placeholder owner_username!")
            else:
                print(f"✅ Owner username looks good: {setting.value}")
        else:
            print("⚠️ No owner_username found in database")
        
        await session.commit()
    
    print("\n" + "="*70)
    print("✅ DONE! Placeholder values removed!")
    print("="*70)
    print("\nNow:")
    print("1. Restart the bot (or redeploy on Koyeb)")
    print("2. Support button will show 'Support Not Configured'")
    print("3. Use /setchannel and /setowner to set YOUR values")
    print("4. Support will then show YOUR values correctly!")
    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(fix_support_now())
