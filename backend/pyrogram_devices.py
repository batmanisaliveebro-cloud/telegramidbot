"""
Real device management using Pyrogram
"""
import logging
from pyrogram import Client
from pyrogram.errors import RPCError
from datetime import datetime

logger = logging.getLogger(__name__)

async def get_active_sessions(session_string: str, api_id: int, api_hash: str):
    """
    Get active sessions/devices for an account using Pyrogram
    Returns list of dicts with device info
    """
    devices = []
    
    try:
        # Create Pyrogram client from session string
        async with Client(
            "temp_session",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        ) as client:
            # Get active authorizations (sessions)
            authorizations = await client.get_authorizations()
            
            for i, auth in enumerate(authorizations, 1):
                device_info = {
                    "id": i,
                    "hash": auth.hash,  # For termination
                    "device_model": auth.device_model or "Unknown Device",
                    "platform": auth.platform or "Unknown",
                    "app_name": auth.app_name or "Telegram",
                    "app_version": auth.app_version or "Unknown",
                    "location": f"{auth.country or 'Unknown'}",
                    "ip_address": auth.ip or "Unknown",
                    "date_created": auth.date_created,
                    "date_active": auth.date_active,
                    "is_current": auth.current,
                }
                
                # Calculate "last seen"
                if auth.current:
                    device_info["last_seen"] = "Active now"
                else:
                    time_diff = datetime.utcnow() - auth.date_active
                    if time_diff.seconds < 60:
                        device_info["last_seen"] = f"{time_diff.seconds} seconds ago"
                    elif time_diff.seconds < 3600:
                        device_info["last_seen"] = f"{time_diff.seconds // 60} minutes ago"
                    elif time_diff.days == 0:
                        device_info["last_seen"] = f"{time_diff.seconds // 3600} hours ago"
                    else:
                        device_info["last_seen"] = f"{time_diff.days} days ago"
                
                devices.append(device_info)
                
    except RPCError as e:
        logger.error(f"Pyrogram error getting sessions: {e}")
        raise Exception(f"Failed to fetch sessions: {e}")
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise
    
    return devices


async def terminate_session(session_string: str, api_id: int, api_hash: str, session_hash: int):
    """
    Terminate a specific session/device using Pyrogram
    """
    try:
        async with Client(
            "temp_session",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        ) as client:
            # Terminate the specific authorization
            await client.terminate_authorization(session_hash)
            logger.info(f"✅ Terminated session with hash: {session_hash}")
            return True
            
    except RPCError as e:
        logger.error(f"Pyrogram error terminating session: {e}")
        raise Exception(f"Failed to terminate session: {e}")
    except Exception as e:
        logger.error(f"Error terminating session: {e}")
        raise


async def terminate_all_except_current(session_string: str, api_id: int, api_hash: str):
    """
    Terminate all sessions except the current one
    """
    try:
        async with Client(
            "temp_session",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        ) as client:
            # Terminate all other sessions
            result = await client.terminate_all_authorizations()
            logger.info(f"✅ Terminated all other sessions")
            return result
            
    except RPCError as e:
        logger.error(f"Pyrogram error terminating all sessions: {e}")
        raise Exception(f"Failed to terminate all sessions: {e}")
    except Exception as e:
        logger.error(f"Error terminating all sessions: {e}")
        raise
