import asyncio
from pyrogram import Client
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DeviceManager:
    def __init__(self):
        # Allow fallback to main bot credentials if specific user creds aren't available
        # (Though usually session strings bind to the App ID they were created with, 
        # Pyrogram is often forgiving if only hash/id matches the string's format)
        self.api_id = os.getenv("API_ID") or os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("API_HASH") or os.getenv("TELEGRAM_API_HASH")
        
        if not self.api_id or not self.api_hash:
            logger.warning("API_ID or API_HASH not found in environment for DeviceManager")

    async def get_active_sessions(self, session_string: str):
        """Fetch active sessions for the given account"""
        client = Client(
            name="temp_device_check",
            api_id=self.api_id,
            api_hash=self.api_hash,
            session_string=session_string,
            in_memory=True,
            no_updates=True
        )
        
        try:
            logger.info("Connecting to Telegram to fetch sessions...")
            await client.connect()
            
            # Fetch authorizations (active sessions) using Pyrogram's raw API
            from pyrogram.raw.functions.account import GetAuthorizations
            authorizations_obj = await client.invoke(GetAuthorizations())
            authorizations = authorizations_obj.authorizations
            
            # Get current session info to identify "This Device"
            me = await client.get_me()
            current_auth = None
            
            # Filter/Process
            results = []
            for auth in authorizations:
                # Format dates safely
                date_created = datetime.fromtimestamp(auth.date_created) if hasattr(auth, 'date_created') else None
                date_active = datetime.fromtimestamp(auth.date_active) if hasattr(auth, 'date_active') else None
                
                results.append({
                    "hash": auth.hash,
                    "device_model": getattr(auth, 'device_model', 'Unknown'),
                    "platform": getattr(auth, 'platform', 'Unknown'),
                    "system_version": getattr(auth, 'system_version', 'Unknown'),
                    "api_id": auth.api_id,
                    "app_name": auth.app_name,
                    "app_version": auth.app_version,
                    "date_created": date_created,
                    "date_active": date_active,
                    "ip": auth.ip,
                    "country": auth.country,
                    "region": getattr(auth, 'region', ''),
                    "is_current": getattr(auth, 'current', False)
                })
                
            return results
            
        except Exception as e:
            logger.error(f"Error fetching sessions: {e}")
            raise e
        finally:
            if client.is_connected:
                await client.disconnect()

    async def terminate_session(self, session_string: str, hash_id: int):
        """Terminate a specific session by hash"""
        client = Client(
            name="temp_device_kill",
            api_id=self.api_id,
            api_hash=self.api_hash,
            session_string=session_string,
            in_memory=True,
            no_updates=True
        )
        
        try:
            logger.info(f"Connecting to terminate session hash: {hash_id}")
            await client.connect()
            
            # Delete authorization using Pyrogram's raw API
            from pyrogram.raw.functions.account import ResetAuthorization
            await client.invoke(ResetAuthorization(hash=hash_id))
            return True
        except Exception as e:
            logger.error(f"Error terminating session: {e}")
            raise e
        finally:
            if client.is_connected:
                await client.disconnect()
