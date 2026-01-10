"""
Automatic Webhook Health Monitor
Runs in background and auto-fixes webhook if it disconnects
"""
import asyncio
import logging
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

class WebhookMonitor:
    def __init__(self, bot_token: str, webhook_url: str, check_interval: int = 300):
        """
        Initialize webhook monitor
        
        Args:
            bot_token: Telegram bot token
            webhook_url: Expected webhook URL
            check_interval: Check every N seconds (default: 300 = 5 minutes)
        """
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.check_interval = check_interval
        self.is_running = False
        
    async def check_webhook_health(self) -> bool:
        """Check if webhook is correctly set"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.bot_token}/getWebhookInfo"
                async with session.get(url) as response:
                    data = await response.json()
                    
                    if data.get('ok'):
                        info = data['result']
                        current_url = info.get('url', '')
                        pending = info.get('pending_update_count', 0)
                        last_error = info.get('last_error_message')
                        
                        # Check if webhook is healthy
                        is_healthy = (
                            current_url == self.webhook_url and
                            pending < 100 and  # Not too many pending updates
                            not last_error  # No recent errors
                        )
                        
                        if not is_healthy:
                            logger.warning(
                                f"⚠️ Webhook unhealthy: "
                                f"URL={current_url}, "
                                f"Expected={self.webhook_url}, "
                                f"Pending={pending}, "
                                f"Error={last_error}"
                            )
                        
                        return is_healthy
                    
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            return False
    
    async def fix_webhook(self) -> bool:
        """Automatically fix webhook if it's broken"""
        try:
            logger.info("🔧 Auto-fixing webhook...")
            
            async with aiohttp.ClientSession() as session:
                # Step 1: Delete old webhook
                delete_url = f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook"
                async with session.post(delete_url, json={"drop_pending_updates": True}) as response:
                    delete_result = await response.json()
                    logger.info(f"🗑️ Deleted old webhook: {delete_result.get('ok', False)}")
                
                # Wait for Telegram to process
                await asyncio.sleep(2)
                
                # Step 2: Set new webhook
                set_url = f"https://api.telegram.org/bot{self.bot_token}/setWebhook"
                webhook_data = {
                    "url": self.webhook_url,
                    "drop_pending_updates": True,
                    "max_connections": 100,
                    "allowed_updates": ["message", "callback_query"]
                }
                
                async with session.post(set_url, json=webhook_data) as response:
                    set_result = await response.json()
                    
                    if set_result.get('ok'):
                        logger.info(f"✅ Webhook auto-fixed: {self.webhook_url}")
                        return True
                    else:
                        logger.error(f"❌ Failed to set webhook: {set_result}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Auto-fix error: {e}")
            return False
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info(f"🔍 Webhook monitor started (checking every {self.check_interval}s)")
        
        while self.is_running:
            try:
                # Check webhook health
                is_healthy = await self.check_webhook_health()
                
                if not is_healthy:
                    logger.warning("⚠️ Webhook is unhealthy, attempting auto-fix...")
                    success = await self.fix_webhook()
                    
                    if success:
                        logger.info("✅ Webhook auto-fixed successfully!")
                    else:
                        logger.error("❌ Auto-fix failed, will retry next cycle")
                else:
                    logger.info(f"✅ Webhook healthy ({datetime.now().strftime('%H:%M:%S')})")
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Monitor loop error: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def start(self):
        """Start the monitoring"""
        if self.is_running:
            logger.warning("⚠️ Monitor already running")
            return
        
        self.is_running = True
        await self.monitor_loop()
    
    def stop(self):
        """Stop the monitoring"""
        self.is_running = False
        logger.info("🛑 Webhook monitor stopped")
