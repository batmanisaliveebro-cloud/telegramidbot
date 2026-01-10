"""
Check webhook status for Telegram bot
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def check_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            
            print("="*60)
            print("WEBHOOK STATUS")
            print("="*60)
            
            if data['ok']:
                info = data['result']
                print(f"✅ Webhook URL: {info.get('url', 'NOT SET')}")
                print(f"📊 Pending Updates: {info.get('pending_update_count', 0)}")
                print(f"🕒 Last Error Date: {info.get('last_error_date', 'None')}")
                print(f"❌ Last Error: {info.get('last_error_message', 'None')}")
                print(f"🔢 Max Connections: {info.get('max_connections', 0)}")
                
                if info.get('last_error_message'):
                    print("\n🚨 WEBHOOK HAS ERRORS!")
                    print(f"Error: {info['last_error_message']}")
                    
                if not info.get('url'):
                    print("\n🚨 WEBHOOK NOT SET!")
                    
            else:
                print(f"❌ API Error: {data}")
            
            print("="*60)

if __name__ == "__main__":
    asyncio.run(check_webhook())
