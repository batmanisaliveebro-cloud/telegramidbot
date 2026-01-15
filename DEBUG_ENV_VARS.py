"""
EMERGENCY: Debug why environment variables aren't working
This will show exactly what the bot is seeing
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*70)
print("ENVIRONMENT VARIABLE DEBUG")
print("="*70)

# Check what values are set
channel = os.getenv("BOT_CHANNEL_LINK", "NOT_SET")
owner = os.getenv("BOT_OWNER_USERNAME", "NOT_SET")

print(f"\nBOT_CHANNEL_LINK = {channel}")
print(f"BOT_OWNER_USERNAME = {owner}")

print("\n" + "="*70)
print("DIAGNOSIS:")
print("="*70)

if channel == "NOT_SET":
    print("❌ BOT_CHANNEL_LINK is NOT SET!")
    print("   Solution: Add it to Koyeb environment variables")
elif "yourchannel" in channel.lower():
    print("❌ BOT_CHANNEL_LINK has placeholder value!")
    print(f"   Current value: {channel}")
    print("   Solution: Change it on Koyeb to your actual channel")
else:
    print(f"✅ BOT_CHANNEL_LINK looks good: {channel}")

if owner == "NOT_SET":
    print("❌ BOT_OWNER_USERNAME is NOT SET!")
    print("   Solution: Add it to Koyeb environment variables")
elif "yourusername" in owner.lower() or "yourchannel" in owner.lower():
    print("❌ BOT_OWNER_USERNAME has placeholder value!")
    print(f"   Current value: {owner}")
    print("   Solution: Change it on Koyeb to your actual username")
else:
    print(f"✅ BOT_OWNER_USERNAME looks good: {owner}")

print("\n" + "="*70)
print("CRITICAL CHECKS:")
print("="*70)
print("\n1. Did you set these on KOYEB (not in local .env)?")
print("2. Did you REDEPLOY after setting them?")
print("3. Did you wait 2-3 minutes for deployment to complete?")
print("4. Environment variable names are CASE-SENSITIVE!")
print("   - Must be exactly: BOT_CHANNEL_LINK")
print("   - Must be exactly: BOT_OWNER_USERNAME")
print("\n" + "="*70)
