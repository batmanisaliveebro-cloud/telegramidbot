"""
Telegram Session Manager for OTP Interception
Handles Pyrogram clients to monitor incoming messages and extract OTP codes
"""

from pyrogram import Client, filters
from pyrogram.types import Message
import asyncio
from typing import Dict, Optional
import re
import os
from datetime import datetime, timedelta

class TelegramSessionManager:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients: Dict[str, Client] = {}
        self.otp_cache: Dict[str, dict] = {}  # phone -> {code, timestamp}
        self.login_status: Dict[str, bool] = {}  # phone -> is_logged_in
        self.monitoring_start_times: Dict[str, datetime] = {} # phone -> start_time
        
    async def start_monitoring(self, phone_number: str, session_string: str):
        """Start monitoring a Telegram session for OTP codes"""
        if phone_number in self.active_clients:
            print(f"Already monitoring {phone_number}")
            # Reset start time on re-monitor request to be safe, or keep old?
            # Better to update it so we don't catch old messages if restarted
            self.monitoring_start_times[phone_number] = datetime.now()
            return
        
        try:
            # Clean phone number for session name
            clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            client_name = f"session_{clean_phone}"
            
            # Create Pyrogram client with session string
            client = Client(
                name=client_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                session_string=session_string,
                in_memory=True  # Don't save session to file
            )
            
            # Message handler for OTP codes from Telegram
            # REMOVED FILTER to debug all messages
            @client.on_message()  # Capture ALL messages for debugging
            async def handle_telegram_message(client: Client, message: Message):
                try:
                    text = getattr(message, "text", "") or getattr(message, "caption", "") or ""
                    
                    sender = None
                    try:
                        sender = message.from_user
                    except Exception:
                        pass
                        
                    sender_id = sender.id if sender else 0
                    sender_name = sender.first_name if sender else "Unknown"
                    
                    # IGNORE SPAM: If it's a channel post or invalid peer, we might crash accessing props
                    # So we just safely try to get text and sender
                    
                    # Logic: We mostly care about 777000 (Telegram)
                    is_telegram = sender_id == 777000
                    
                    # Also check content for "Login code" just in case sender ID is weird
                    is_otp_text = "login code" in text.lower() or "telegram code" in text.lower() or "verification code" in text.lower()

                    if is_telegram or is_otp_text:
                        print(f"\n🔔 [IMPORTANT] MESSAGE FROM {sender_id} ({sender_name})")
                        print(f"📄 Text: {text}")
                        
                        # Extract OTP
                        otp_match = re.search(r'\b\d{5,6}\b', text)
                        if otp_match:
                            otp_code = otp_match.group()
                            self.otp_cache[phone_number] = {
                                'code': otp_code,
                                'timestamp': datetime.now(),
                                'message': text
                            }
                            print(f"✅ OTP CAPTURED for {phone_number}: {otp_code}")
                        else:
                            print(f"⚠️ Message from Telegram but no code found!")
                            
                    elif "peer id invalid" in text.lower():
                        # Ignore this specific internal error if it leaks into text (unlikely but safe)
                        pass
                        
                except Exception as e:
                    # Ignore PeerIdInvalid errors completely to keep logs clean
                    if "peer" in str(e).lower():
                        return
                    print(f"⚠️ Handler Error: {e}")
            
            # Start the client
            await client.start()
            
            # Verify who we are logged in as (Best effort, ignore FLOOD_WAIT)
            try:
                me = await client.get_me()
                print(f"🟢 Started monitoring {phone_number}")
                print(f"👤 Logged in as: {me.first_name} (ID: {me.id})")
                print(f"📱 Account Phone: {me.phone_number}")
            except Exception as e:
                print(f"⚠️ Could not fetch user details (likely FloodWait): {e}")
                print(f"🟢 Started monitoring {phone_number} (User details skipped)")
            
            self.active_clients[phone_number] = client
            self.login_status[phone_number] = False
            
        except Exception as e:
            print(f"❌ Error starting monitoring for {phone_number}: {str(e)}")
            raise
    
    async def stop_monitoring(self, phone_number: str):
        """Stop monitoring a session"""
        if phone_number in self.active_clients:
            try:
                await self.active_clients[phone_number].stop()
                del self.active_clients[phone_number]
                print(f"🔴 Stopped monitoring {phone_number}")
            except Exception as e:
                print(f"Error stopping {phone_number}: {e}")
        
        # Clear cache
        if phone_number in self.otp_cache:
            del self.otp_cache[phone_number]
        if phone_number in self.login_status:
            del self.login_status[phone_number]
    
    async def check_latest_otp(self, phone_number: str) -> Optional[str]:
        """
        Actively check the latest message from Telegram (777000) for an OTP.
        This bypasses the need for waiting on incoming updates.
        """
        if phone_number not in self.active_clients:
            return None
            
        client = self.active_clients[phone_number]
        try:
            print(f"🔄 Actively checking history for {phone_number}...")
            # Fetch latest message from Telegram (777000)
            # 777000 is the official notification user ID
            async for message in client.get_chat_history(777000, limit=1):
                text = getattr(message, "text", "") or getattr(message, "caption", "") or ""
                print(f"📄 Latest Telegram Message: {text[:100]}...")
                
                # Check for OTP pattern
                otp_match = re.search(r'\b\d{5,6}\b', text)
                if otp_match:
                    otp_code = otp_match.group()
                    
                    # Verify it's recent (within 5 mins)
                    msg_date = message.date
                    if datetime.now() - msg_date < timedelta(minutes=5):
                        print(f"✅ Found Valid OTP in history: {otp_code}")
                        
                        # Cache it
                        self.otp_cache[phone_number] = {
                            'code': otp_code,
                            'timestamp': datetime.now(),
                            'message': text
                        }
                        return otp_code
                    else:
                        print(f"⚠️ Found OTP but it is too old: {otp_code}")
        except Exception as e:
             print(f"⚠️ Error checking active history: {e}")
             
        # Also check cache as backup
        return self.get_otp(phone_number)
    
    def get_otp(self, phone_number: str) -> Optional[str]:
        """Get cached OTP for a phone number"""
        if phone_number in self.otp_cache:
            otp_data = self.otp_cache[phone_number]
            # Check if OTP is less than 5 minutes old
            if datetime.now() - otp_data['timestamp'] < timedelta(minutes=5):
                return otp_data['code']
        return None
    
    def clear_otp(self, phone_number: str):
        """Clear OTP from cache"""
        if phone_number in self.otp_cache:
            del self.otp_cache[phone_number]
    
    async def check_login_status(self, phone_number: str) -> str:
        """
        Check if user successfully logged in
        Returns: "LOGGED_IN", "WAITING", "NOT_MONITORING"
        """
        if phone_number not in self.active_clients:
            return "NOT_MONITORING"
        
        # If we already detected login, return immediately
        if self.login_status.get(phone_number, False):
            return "LOGGED_IN"
        
        try:
            client = self.active_clients[phone_number]
            
            # Try to get user's own info - if this works, session is active
            me = await client.get_me()
            if me:
                # Session is active. Now check if there is a NEW login from the user
                try:
                    # Check recent messages from Telegram for "New login" or success indicators
                    found_login = False
                    async for message in client.get_chat_history(777000, limit=5):
                        text = (getattr(message, "text", "") or getattr(message, "caption", "") or "").lower()
                        
                        # Keywords for successful login by user
                        # Telegram usually sends: "New login", "Login code", etc.
                        # If we see a login notification that is VERY recent (last 2 mins), it's likely the user
                        if "login" in text and ("new" in text or "device" in text or "successfully" in text):
                            # Only accept if message is NEWER than when we started monitoring
                            start_time = self.monitoring_start_times.get(phone_number, datetime.min)
                            if message.date > start_time:
                                found_login = True
                                print(f"✅ DETECTED NEW LOGIN MSG: {text[:50]}...")
                                break
                            else:
                                print(f"⚠️ Ignoring old login msg from {message.date} (Started: {start_time})")
                    
                    if found_login:
                        self.login_status[phone_number] = True
                        return "LOGGED_IN"
                        
                except Exception as e:
                    print(f"Error checking login messages: {e}")

                # Session is still active, user hasn't logged in from another device yet
                return "WAITING"
                
        except Exception as e:
            error_str = str(e).lower()
            # If we get AUTH_KEY_UNREGISTERED, user logged in from another device
            if "auth_key_unregistered" in error_str or "session" in error_str:
                self.login_status[phone_number] = True
                return "LOGGED_IN"
            # Other errors
            print(f"Error checking login for {phone_number}: {e}")
            return "WAITING"
        
        return "WAITING"
    
    async def test_session(self, phone_number: str, session_string: str) -> dict:
        """
        Test if a session is valid and active
        Returns: {success: bool, status: str, user_info: dict}
        """
        try:
            clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            test_client = Client(
                name=f"test_{clean_phone}",
                api_id=self.api_id,
                api_hash=self.api_hash,
                session_string=session_string,
                in_memory=True
            )
            
            await test_client.start()
            
            # Get user info
            me = await test_client.get_me()
            
            user_info = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name or "",
                "username": me.username or "N/A",
                "phone": me.phone_number
            }
            
            await test_client.stop()
            
            return {
                "success": True,
                "status": "ACTIVE",
                "user_info": user_info
            }
            
        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "message": str(e)
            }
    
    def get_active_sessions_count(self) -> int:
        """Get count of currently active monitoring sessions"""
        return len(self.active_clients)
    
    def get_all_active_phones(self) -> list:
        """Get list of all phones being monitored"""
        return list(self.active_clients.keys())


# Global session manager instance
_session_manager = None

def get_session_manager():
    """Get or create global session manager instance"""
    global _session_manager
    if _session_manager is None:
        api_id = int(os.getenv("TELEGRAM_API_ID", 0))
        api_hash = os.getenv("TELEGRAM_API_HASH", "")
        if not api_id or not api_hash:
            raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment")
        _session_manager = TelegramSessionManager(api_id, api_hash)
    return _session_manager
