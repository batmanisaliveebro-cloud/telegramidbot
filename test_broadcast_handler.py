"""
Test if broadcast handler is correctly registered
Run this to verify the handler exists
"""
import sys
sys.path.insert(0, 'backend')

# Check if handler is defined
with open('backend/bot.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
print("Checking broadcast handler...")
print("="*60)

# Check for handler decorator
if '@dp.callback_query(F.data == "btn_broadcast")' in content:
    print("✅ Broadcast callback handler FOUND")
else:
    print("❌ Broadcast callback handler NOT FOUND")

# Check for function definition
if 'async def cmd_broadcast' in content:
    print("✅ cmd_broadcast function FOUND")
else:
    print("❌ cmd_broadcast function NOT FOUND")

# Check for button in menu
if 'InlineKeyboardButton(text="📢 Broadcast"' in content:
    print("✅ Broadcast button in menu FOUND")
else:
    print("❌ Broadcast button in menu NOT FOUND")

# Check for state
if 'class BroadcastMessageStates' in content:
    print("✅ BroadcastMessageStates class FOUND")
else:
    print("❌ BroadcastMessageStates class NOT FOUND")

# Check for message handler
if '@dp.message(BroadcastMessageStates.waiting_for_message)' in content:
    print("✅ Broadcast message handler FOUND")
else:
    print("❌ Broadcast message handler NOT FOUND")

print("="*60)

# Look for syntax errors
try:
    compile(content, 'backend/bot.py', 'exec')
    print("✅ NO SYNTAX ERRORS")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
    print(f"   Line {e.lineno}: {e.text}")
