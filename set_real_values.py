"""
EMERGENCY FIX: Update channel and owner directly in database
This script will replace @YourChannel placeholder with YOUR actual values
"""
import asyncio
from backend.database import async_session
from backend.models import Settings
from sqlalchemy import select

async def emergency_fix():
    print("\n" + "="*60)
    print("EMERGENCY DATABASE FIX - Replace Placeholder Values")
    print("="*60)
    
    # YOUR ACTUAL VALUES - EDIT THESE!
    YOUR_CHANNEL_LINK = "https://t.me/YOUR_ACTUAL_CHANNEL"  # ← CHANGE THIS!
    YOUR_OWNER_USERNAME = "@YOUR_ACTUAL_USERNAME"           # ← CHANGE THIS!
    
    print(f"\n📢 Will set Channel Link to: {YOUR_CHANNEL_LINK}")
    print(f"👤 Will set Owner Username to: {YOUR_OWNER_USERNAME}")
    
    if "YOUR_ACTUAL" in YOUR_CHANNEL_LINK or "YOUR_ACTUAL" in YOUR_OWNER_USERNAME:
        print("\n⚠️  ERROR: You need to edit this file first!")
        print("Open: set_real_values.py")
        print("Edit lines 11-12 with YOUR real values")
        print("Then run again!")
        return
    
    confirm = input("\n✅ Are these correct? (yes/no): ")
    if confirm.lower() != "yes":
        print("❌ Cancelled. Edit the file and try again.")
        return
    
    async with async_session() as session:
        # Update Channel Link
        stmt = select(Settings).where(Settings.key == "bot_channel_link")
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()
        
        if setting:
            old_value = setting.value
            setting.value = YOUR_CHANNEL_LINK
            print(f"\n✅ UPDATED channel_link")
            print(f"   Old: {old_value}")
            print(f"   New: {YOUR_CHANNEL_LINK}")
        else:
            session.add(Settings(key="bot_channel_link", value=YOUR_CHANNEL_LINK))
            print(f"\n✅ CREATED channel_link: {YOUR_CHANNEL_LINK}")
        
        # Update Owner Username
        stmt2 = select(Settings).where(Settings.key == "bot_owner_username")
        res2 = await session.execute(stmt2)
        setting2 = res2.scalar_one_or_none()
        
        if setting2:
            old_value2 = setting2.value
            setting2.value = YOUR_OWNER_USERNAME
            print(f"\n✅ UPDATED owner_username")
            print(f"   Old: {old_value2}")
            print(f"   New: {YOUR_OWNER_USERNAME}")
        else:
            session.add(Settings(key="bot_owner_username", value=YOUR_OWNER_USERNAME))
            print(f"\n✅ CREATED owner_username: {YOUR_OWNER_USERNAME}")
        
        await session.commit()
        
        print("\n" + "="*60)
        print("SUCCESS! Database updated!")
        print("="*60)
        print("\nNow do these steps:")
        print("1. If running locally: Restart the bot")
        print("2. If on Koyeb: Wait for auto-redeploy OR manually redeploy")
        print("3. Test by clicking '🆘 Support' button in bot")
        print("\nIt should now show YOUR channel and username!")

if __name__ == "__main__":
    asyncio.run(emergency_fix())
