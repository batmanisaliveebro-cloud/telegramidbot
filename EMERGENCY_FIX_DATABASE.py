"""
EMERGENCY FIX - Run this to set YOUR channel and owner in database
This will FIX the support button immediately!
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def emergency_fix():
    from backend.database import async_session
    from backend.models import Settings
    from sqlalchemy import select
    
    print("\n" + "="*70)
    print("EMERGENCY FIX - SETTING YOUR VALUES IN DATABASE")
    print("="*70)
    
    # GET VALUES FROM USER
    print("\nEnter YOUR actual values (NOT placeholders!):")
    print("-" * 70)
    
    channel_link = input("\n📢 Enter your Telegram channel link (e.g., https://t.me/mychannel): ").strip()
    owner_username = input("👤 Enter your Telegram username (e.g., @myname): ").strip()
    
    if not channel_link or not owner_username:
        print("\n❌ ERROR: You must enter both values!")
        return
    
    if not channel_link.startswith("http"):
        print("\n❌ ERROR: Channel link must start with https://")
        return
    
    if not owner_username.startswith("@"):
        print("\n❌ ERROR: Username must start with @")
        return
    
    print("\n" + "="*70)
    print("UPDATING DATABASE...")
    print("="*70)
    
    async with async_session() as session:
        # DELETE old settings first
        from sqlalchemy import delete
        await session.execute(delete(Settings).where(Settings.key == "bot_channel_link"))
        await session.execute(delete(Settings).where(Settings.key == "bot_owner_username"))
        await session.commit()
        print("\n✅ Deleted old placeholder values")
        
        # INSERT new values
        session.add(Settings(key="bot_channel_link", value=channel_link))
        session.add(Settings(key="bot_owner_username", value=owner_username))
        await session.commit()
        print(f"✅ Set channel_link to: {channel_link}")
        print(f"✅ Set owner_username to: {owner_username}")
    
    print("\n" + "="*70)
    print("SUCCESS! DATABASE UPDATED!")
    print("="*70)
    print("\nNow do this:")
    print("1. If running locally: Restart the bot")
    print("2. If on Koyeb: It will auto-restart, wait 30 seconds")
    print("3. Click 'Support' button in bot")
    print("4. Should show YOUR channel and username!")
    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(emergency_fix())
