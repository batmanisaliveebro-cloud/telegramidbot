"""
Force reset webhook for Telegram bot
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://doubtful-chelsae-decstorroyal-43b44335.koyeb.app/webhook"

async def reset_webhook():
    # First delete webhook
    delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(delete_url) as response:
            data = await response.json()
            print(f"🗑️ Delete webhook: {data}")
        
        await asyncio.sleep(2)
        
        # Then set new webhook
        set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        params = {
            "url": WEBHOOK_URL,
            "drop_pending_updates": True  # Clear old pending messages
        }
        
        async with session.post(set_url, json=params) as response:
            data = await response.json()
            print(f"✅ Set webhook: {data}")
            
        await asyncio.sleep(2)
        
        # Verify
        check_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        async with session.get(check_url) as response:
            data = await response.json()
            if data['ok']:
                info = data['result']
                print(f"\n✅ Webhook URL: {info.get('url')}")
                print(f"📊 Pending: {info.get('pending_update_count')}")

if __name__ == "__main__":
    asyncio.run(reset_webhook())
    print("\n🎯 Webhook reset complete! Try /start now!")
