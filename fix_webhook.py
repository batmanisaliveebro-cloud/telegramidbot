import requests

BOT_TOKEN = "8220540161:AAEDKjtZrmKimiXffkAHy0vG8KANCaOdS4E"
WEBHOOK_URL = "https://shallow-reggie-telegrambotmine-8d891f24.koyeb.app/webhook"

# Set webhook
response = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={
        "url": WEBHOOK_URL,
        "drop_pending_updates": True
    }
)

print("=== SET WEBHOOK RESPONSE ===")
print(response.json())
print()

# Get webhook info
info_response = requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
)

print("=== CURRENT WEBHOOK INFO ===")
print(info_response.json())
