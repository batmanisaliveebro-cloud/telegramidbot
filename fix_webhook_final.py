"""
Force set webhook for Telegram bot
"""
import requests

BOT_TOKEN = "8220540161:AAEDKjtZrmKimiXffkAHy0vG8KANCaOdS4E"
WEBHOOK_URL = "https://doubtful-chelsae-decstorroyal-43b44335.koyeb.app/webhook"

print("🔄 Deleting old webhook...")
delete_response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
print(f"Delete result: {delete_response.json()}")

print("\n⏳ Setting new webhook...")
set_response = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={
        "url": WEBHOOK_URL,
        "drop_pending_updates": True,  # Clear any stuck messages
        "max_connections": 40
    }
)
print(f"Set result: {set_response.json()}")

print("\n✅ Verifying webhook...")
info_response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
info = info_response.json()
if info['ok']:
    result = info['result']
    print(f"URL: {result.get('url')}")
    print(f"Pending updates: {result.get('pending_update_count')}")
    print(f"Last error: {result.get('last_error_message', 'None')}")
    
    if result.get('url') == WEBHOOK_URL:
        print("\n🎉 WEBHOOK CONFIGURED SUCCESSFULLY!")
        print("Try sending /start to @AKHILESCROWTGBOT now!")
    else:
        print(f"\n❌ URL mismatch! Expected {WEBHOOK_URL}, got {result.get('url')}")
else:
    print(f"❌ Error: {info}")
