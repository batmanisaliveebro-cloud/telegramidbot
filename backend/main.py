from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import init_db, async_session
from .bot import bot, dp
from .models import User, Country, Account, Purchase, Deposit, Settings
from aiogram.types import Update
from .session_manager import get_session_manager
from .session_generator_service import get_session_generator
from sqlalchemy import select, update, delete
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import os
from fastapi import UploadFile, File, Form
import aiohttp # For webhook setup in startup event
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- Schemas ---
class CountryCreate(BaseModel):
    name: str
    emoji: str
    price: float

class AccountCreate(BaseModel):
    country_id: int
    phone_number: str
    session_data: str
    type: str = "ID"
    twofa_password: str | None = None

class DepositUpdate(BaseModel):
    status: str # APPROVED, REJECTED

class LoginRequest(BaseModel):
    password: str

class BalanceAdjustment(BaseModel):
    amount: float
    reason: str  # "admin_add" or "admin_deduct"

# Webhook Configuration
WEBHOOK_PATH = "/webhook"
# BASE_WEBHOOK_URL must be set as environment variable on Koyeb
# Example: BASE_WEBHOOK_URL=https://your-app-name.koyeb.app

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    await init_db()
    
    # Set Webhook on Startup with error handling
    try:
        base_url = os.getenv("BASE_WEBHOOK_URL")
        
        if not base_url:
            print("❌ ERROR: BASE_WEBHOOK_URL environment variable not set!", flush=True)
            print("   Set it on Koyeb to your app URL", flush=True)
        else:
            webhook_url = f"{base_url.rstrip('/')}{WEBHOOK_PATH}"
            print(f"🔄 Setting webhook to: {webhook_url}", flush=True)
            
            await bot.set_webhook(
                url=webhook_url,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=True
            )
            
            # Verify Webhook
            info = await bot.get_webhook_info()
            print(f"✅ Webhook set successfully!", flush=True)
            print(f"   URL: {info.url}", flush=True)
            print(f"   Pending updates: {info.pending_update_count}", flush=True)
            
            if info.last_error_message:
                print(f"⚠️ Last webhook error: {info.last_error_message}", flush=True)
                print(f"   Error date: {info.last_error_date}", flush=True)
            
    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {e}", flush=True)
        print(f"   Bot will continue but webhook may not work!", flush=True)
    
    yield
    
    # Delete Webhook on Shutdown
    try:
        await bot.delete_webhook()
    except:
        pass
    await bot.session.close()

app = FastAPI(lifespan=lifespan)


@app.get("/")
async def health_check():
    return {"status": "ok", "mode": "webhook", "service": "Telegram Bot Backend"}


# === CRITICAL: WEBHOOK ENDPOINT ===

@app.post(WEBHOOK_PATH)
async def webhook_handler(update: dict):
    """Receive and process Telegram updates"""
    try:
        telegram_update = Update(**update)
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"ok": False}


@app.post("/api/fix-webhook")
async def fix_webhook_endpoint():
    """
    Manual webhook fix endpoint for admin panel
    Deletes old webhook and sets new one
    """
    try:
        import os
        import aiohttp
        import asyncio
        import logging
        
        logger = logging.getLogger(__name__)
        
        bot_token = os.getenv("BOT_TOKEN")
        base_url = os.getenv("BASE_WEBHOOK_URL")
        
        if not base_url:
            logger.error("❌ BASE_WEBHOOK_URL not set in environment!")
            return {"success": False, "error": "BASE_WEBHOOK_URL not configured"}
        
        webhook_url = f"{base_url.rstrip('/')}/webhook"
        logger.info(f"🔧 Admin requested webhook fix to: {webhook_url}")
        
        async with aiohttp.ClientSession() as session:
            # Delete old webhook
            delete_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
            async with session.post(delete_url, json={"drop_pending_updates": True}) as response:
                delete_result = await response.json()
                logger.info(f"🗑️ Webhook deleted: {delete_result.get('ok', False)}")
            
            # Wait for Telegram to process
            await asyncio.sleep(2)
            
            # Set new webhook
            set_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
            webhook_data = {
                "url": webhook_url,
                "drop_pending_updates": True,
                "max_connections": 100,
                "allowed_updates": ["message", "callback_query"]
            }
            
            async with session.post(set_url, json=webhook_data) as response:
                set_result = await response.json()
                
                if set_result.get('ok'):
                    # Verify webhook
                    verify_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
                    async with session.get(verify_url) as verify_response:
                        verify_data = await verify_response.json()
                        webhook_info = verify_data.get('result', {})
                        
                        logger.info(f"✅ Webhook fixed and verified: {webhook_url}")
                        
                        return {
                            "success": True,
                            "message": "Webhook fixed successfully!",
                            "webhook_info": {
                                "url": webhook_info.get('url'),
                                "pending_updates": webhook_info.get('pending_update_count', 0),
                                "max_connections": webhook_info.get('max_connections', 0)
                            }
                        }
                else:
                    logger.error(f"❌ Failed to set webhook: {set_result}")
                    return {
                        "success": False,
                        "message": f"Failed to set webhook: {set_result.get('description', 'Unknown error')}"
                    }
                    
    except Exception as e:
        logger.error(f"❌ Webhook fix error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

@app.get("/health")
@app.head("/health")  # Support HEAD requests for UptimeRobot
async def detailed_health():
    """Detailed health check with database and webhook verification"""
    health_status = {"status": "healthy", "checks": {}}
    
    # Check database connection
    try:
        async with async_session() as session:
            await session.execute(select(User).limit(1))
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = f"error: {str(e)[:100]}"
    
    # Check webhook
    try:
        info = await bot.get_webhook_info()
        health_status["checks"]["webhook"] = {
            "url": info.url,
            "pending_updates": info.pending_update_count
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["webhook"] = f"error: {str(e)[:100]}"
    
    return health_status

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add timeout middleware for request protection
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import logging

# Get logger for middleware
middleware_logger = logging.getLogger(__name__)

class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to prevent requests from hanging indefinitely.
    Adds timeout protection to all HTTP requests.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        try:
            # Set timeout for request processing (30 seconds max)
            response = await asyncio.wait_for(call_next(request), timeout=30.0)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response
        except asyncio.TimeoutError:
            middleware_logger.error(f"Request timeout: {request.url.path}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=504,
                content={"detail": "Request processing timeout. Please try again."}
            )
        except Exception as e:
            middleware_logger.error(f"Request error: {e}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error. Please try again."}
            )

app.add_middleware(TimeoutMiddleware)


# Webhook Handler
from aiogram.types import Update

@app.post(WEBHOOK_PATH)
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    """
    Handler for Telegram Webhook updates
    """
    print(f"📥 Received Webhook Update: {update}")
    try:
        # Convert dict to aiogram Update object manually to debug validation errors
        aiogram_update = Update(**update)
        return await dp.feed_update(bot, aiogram_update)
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        # Return 200 OK anyway to stop Telegram from retrying endlessly
        return {"status": "error", "message": str(e)}

# Add CORS middleware to allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin API and Frontend serving below

@app.post("/api/login")
async def login(request: LoginRequest):
    """Admin login endpoint - reads password from ADMIN_PASSWORD env var"""
    try:
        # Get admin password from environment variable
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")  # Default fallback
        
        logger.info(f"🔐 Login attempt with password: {request.password[:3]}***")
        logger.info(f"🔐 Expected password from env: {admin_password[:3]}***")
        
        # Check password
        if request.password == admin_password:
            logger.info("✅ Login successful!")
            # Create a simple token (in production, use proper JWT)
            token = "admin_token_" + str(hash(admin_password))
            return {"token": token, "success": True}
        else:
            logger.warning("❌ Login failed - incorrect password")
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")

# COMPATIBILITY: Also support /admin/login endpoint (frontend uses this)
@app.post("/admin/login")
async def admin_login(request: LoginRequest):
    """Admin login - compatibility endpoint, calls main login function"""
    return await login(request)

# --- Admin API Routes ---

@app.get("/admin/countries")
async def get_countries():
    async with async_session() as session:
        result = await session.execute(select(Country))
        return result.scalars().all()

@app.post("/admin/countries")
async def create_country(country: CountryCreate):
    async with async_session() as session:
        db_country = Country(**country.model_dump())
        session.add(db_country)
        await session.commit()
        return db_country

@app.delete("/admin/countries/{country_id}")
async def delete_country(country_id: int):
    async with async_session() as session:
        await session.execute(delete(Country).where(Country.id == country_id))
        await session.commit()
        return {"message": "Country deleted"}

@app.get("/admin/accounts")
async def get_accounts():
    async with async_session() as session:
        result = await session.execute(select(Account))
        return result.scalars().all()

@app.post("/admin/accounts")
async def add_account(account: AccountCreate):
    async with async_session() as session:
        # REMOVED duplicate check - allows restocking same number after sold
        
        db_account = Account(
            country_id=account.country_id,
            phone_number=account.phone_number,
            session_data=account.session_data,
            type=account.type,
            twofa_password=account.twofa_password,
            is_sold=False  # Explicitly ensure new accounts are available
        )
        session.add(db_account)
        await session.commit()
        await session.refresh(db_account)
        return db_account

@app.get("/admin/stats")
async def get_admin_stats():
    """Get dashboard statistics using efficient SQL aggregations"""
    async with async_session() as session:
        # Use SQL COUNT instead of loading all users into memory
        from sqlalchemy import func
        
        # Total Users - use COUNT
        users_count = await session.scalar(select(func.count(User.id)))
        
        # Total Sales - use SUM aggregation
        total_sales_result = await session.scalar(select(func.sum(Purchase.amount)))
        total_sales = total_sales_result if total_sales_result else 0
        
        # Pending Deposits - use COUNT with filter
        pending_count = await session.scalar(
            select(func.count(Deposit.id)).where(Deposit.status == "PENDING")
        )
        
        return {
            "total_users": users_count or 0,
            "total_sales": float(total_sales),
            "pending_deposits": pending_count or 0
        }

@app.get("/admin/settings/payment")
async def get_payment_settings():
    """Fetch current payment settings and bot config"""
    async with async_session() as session:
        upi_res = await session.execute(select(Settings).where(Settings.key == "payment_upi_id"))
        qr_res = await session.execute(select(Settings).where(Settings.key == "payment_qr_image"))
        channel_res = await session.execute(select(Settings).where(Settings.key == "bot_channel_link"))
        owner_res = await session.execute(select(Settings).where(Settings.key == "bot_owner_username"))
        
        upi_id = upi_res.scalar_one_or_none()
        qr_image = qr_res.scalar_one_or_none()
        channel_link = channel_res.scalar_one_or_none()
        owner_username = owner_res.scalar_one_or_none()
        
        return {
            "upi_id": upi_id.value if upi_id else "",
            "qr_image": qr_image.value if qr_image else "",
            "channel_link": channel_link.value if channel_link else "",
            "owner_username": owner_username.value if owner_username else ""
        }

@app.post("/admin/settings/payment")
async def update_payment_settings(
    upi_id: str = Form(""),
    qr_image: UploadFile = File(None),
    channel_link: str = Form(""),
    owner_username: str = Form("")
):
    """Update payment settings and bot configuration"""
    async with async_session() as session:
        # Update or create UPI ID
        upi_stmt = select(Settings).where(Settings.key == "payment_upi_id")
        upi_res = await session.execute(upi_stmt)
        upi_setting = upi_res.scalar_one_or_none()
        
        if upi_setting:
            upi_setting.value = upi_id
        else:
            session.add(Settings(key="payment_upi_id", value=upi_id))
        
        # Update or create channel link
        channel_stmt = select(Settings).where(Settings.key == "bot_channel_link")
        channel_res = await session.execute(channel_stmt)
        channel_setting = channel_res.scalar_one_or_none()
        
        if channel_setting:
            channel_setting.value = channel_link
        else:
            session.add(Settings(key="bot_channel_link", value=channel_link))
        
        # Update or create owner username
        owner_stmt = select(Settings).where(Settings.key == "bot_owner_username")
        owner_res = await session.execute(owner_stmt)
        owner_setting = owner_res.scalar_one_or_none()
        
        if owner_setting:
            owner_setting.value = owner_username
        else:
            session.add(Settings(key="bot_owner_username", value=owner_username))
        
        # Handle QR image upload if provided
        if qr_image and qr_image.filename:
            contents = await qr_image.read()
            base64_encoded = base64.b64encode(contents).decode('utf-8')
            data_uri = f"data:{qr_image.content_type};base64,{base64_encoded}"
            
            qr_stmt = select(Settings).where(Settings.key == "payment_qr_image")
            qr_res = await session.execute(qr_stmt)
            qr_setting = qr_res.scalar_one_or_none()
            
            if qr_setting:
                qr_setting.value = data_uri
            else:
                session.add(Settings(key="payment_qr_image", value=data_uri))
        
        await session.commit()
        return {"status": "success"}

@app.get("/admin/deposits")
async def get_deposits():
    async with async_session() as session:
        result = await session.execute(select(Deposit).order_by(Deposit.created_at.desc()))
        return result.scalars().all()



@app.patch("/admin/deposits/{deposit_id}")
async def update_deposit(deposit_id: int, update_data: DepositUpdate):
    async with async_session() as session:
        stmt = select(Deposit).where(Deposit.id == deposit_id)
        result = await session.execute(stmt)
        deposit = result.scalar_one_or_none()
        
        if not deposit:
            raise HTTPException(status_code=404, detail="Deposit not found")
        
        deposit.status = update_data.status
        
        if update_data.status == "APPROVED":
            # Add balance to user
            user_stmt = select(User).where(User.id == deposit.user_id)
            user_res = await session.execute(user_stmt)
            user = user_res.scalar_one_or_none()
            if user:
                user.balance += deposit.amount
                # Notify user via bot
                try:
                    await bot.send_message(
                        user.telegram_id, 
                        f"<i>✅ Your deposit of ₹{deposit.amount} has been approved! Your new balance is ₹{user.balance}.</i>",
                        parse_mode="HTML"
                    )
                except:
                    pass
        elif update_data.status == "REJECTED":
            # Notify user about rejection with Contact Owner button
            user_stmt = select(User).where(User.id == deposit.user_id)
            user_res = await session.execute(user_stmt)
            user = user_res.scalar_one_or_none()
            if user:
                try:
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    from aiogram.utils.keyboard import InlineKeyboardBuilder
                    
                    builder = InlineKeyboardBuilder()
                    builder.row(InlineKeyboardButton(text="📞 Contact Owner", url="https://t.me/akhilportal"))
                    
                    await bot.send_message(
                        user.telegram_id,
                        f"<i>❌ Your deposit of ₹{deposit.amount} was rejected.\n\n"
                        "Please contact the owner if you think this is a mistake.</i>",
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                except:
                    pass
        
        await session.commit()
        return deposit

@app.post("/admin/users/{user_id}/adjust-balance")
async def adjust_user_balance(user_id: int, adjustment: BalanceAdjustment):
    async with async_session() as session:
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update balance
        old_balance = user.balance
        user.balance += adjustment.amount
        new_balance = user.balance
        
        await session.commit()
        
        # Send notification to user via bot
        try:
            if adjustment.reason == "admin_add":
                message = (
                    f"✅ <b>Balance Credited</b>\n\n"
                    f"💰 Amount: ₹{abs(adjustment.amount)}\n"
                    f"📊 Previous Balance: ₹{old_balance}\n"
                    f"💵 New Balance: ₹{new_balance}\n\n"
                    f"<i>Balance added by admin</i>"
                )
            elif adjustment.reason == "admin_deduct":
                message = (
                    f"⚠️ <b>Balance Debited</b>\n\n"
                    f"💰 Amount: ₹{abs(adjustment.amount)}\n"
                    f"📊 Previous Balance: ₹{old_balance}\n"
                    f"💵 New Balance: ₹{new_balance}\n\n"
                    f"<i>Balance deducted by admin</i>"
                )
            else:
                message = (
                    f"💳 <b>Balance Updated</b>\n\n"
                    f"💰 Change: ₹{adjustment.amount}\n"
                    f"📊 Previous Balance: ₹{old_balance}\n"
                    f"💵 New Balance: ₹{new_balance}"
                )
            
            await bot.send_message(
                user.telegram_id,
                message,
                parse_mode="HTML"
            )
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to send notification: {e}")
        
        return {"status": "success", "user": user, "new_balance": new_balance}


@app.get("/admin/users")
async def get_users():
    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        return result.scalars().all()

@app.get("/admin/users/{user_id}")
async def get_user_details(user_id: int):
    async with async_session() as session:
        # Get user
        user_stmt = select(User).where(User.id == user_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get purchases
        pur_stmt = select(Purchase).where(Purchase.user_id == user_id).order_by(Purchase.created_at.desc())
        pur_res = await session.execute(pur_stmt)
        purchases = pur_res.scalars().all()
        
        # Get deposits
        dep_stmt = select(Deposit).where(Deposit.user_id == user_id).order_by(Deposit.created_at.desc())
        dep_res = await session.execute(dep_stmt)
        deposits = dep_res.scalars().all()
        
        return {
            "user": user,
            "purchases": purchases,
            "deposits": deposits
        }

# --- Session Testing & OTP Monitoring Endpoints ---

@app.post("/admin/test-session/{account_id}")
async def test_session(account_id: int):
    """Test if a Telegram session is still active"""
    async with async_session() as session:
        stmt = select(Account).where(Account.id == account_id)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if not account.session_data:
            return {
                "success": False,
                "status": "NO_SESSION",
                "message": "No session data available for this account"
            }
        
        try:
            session_mgr = get_session_manager()
            result = await session_mgr.test_session(
                phone_number=account.phone_number,
                session_string=account.session_data
            )
            
            # Update account with test result
            if result["success"]:
                account.session_status = "ACTIVE"
                account.last_health_check = datetime.now()
                account.health_check_message = f"Active - {result['user_info']['first_name']}"
            else:
                account.session_status = "ERROR"
                account.health_check_message = result.get("message", "Unknown error")
            
            await session.commit()
            return result
            
        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "message": str(e)
            }

@app.post("/admin/start-otp-monitor/{account_id}")
async def start_otp_monitoring(account_id: int):
    """Start listening for OTP codes on a specific account"""
    async with async_session() as session:
        stmt = select(Account).where(Account.id == account_id)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if not account.session_data:
            raise HTTPException(status_code=400, detail="No session data available")
        
        try:
            session_mgr = get_session_manager()
            await session_mgr.start_monitoring(
                phone_number=account.phone_number,
                session_string=account.session_data
            )
            return {"success": True, "message": f"Monitoring started for {account.phone_number}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/stop-otp-monitor/{account_id}")
async def stop_otp_monitoring(account_id: int):
    """Stop listening for OTP codes"""
    async with async_session() as session:
        stmt = select(Account).where(Account.id == account_id)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        try:
            session_mgr = get_session_manager()
            await session_mgr.stop_monitoring(account.phone_number)
            return {"success": True, "message": "Monitoring stopped"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/otp-monitor/live")
async def get_live_otp_codes():
    """Get all active OTP monitoring sessions and recent codes"""
    try:
        session_mgr = get_session_manager()
        active_phones = session_mgr.get_all_active_phones()
        
        # Get recent OTPs (last 5 minutes)
        recent_otps = []
        for phone in active_phones:
            otp = session_mgr.get_otp(phone)
            if otp:
                recent_otps.append({
                    "phone": phone,
                    "code": otp,
                    "time_ago": "Just now"
                })
        
        return {
            "active_sessions": session_mgr.get_active_sessions_count(),
            "otps": recent_otps,
            "pending_requests": 0  # TODO: Track pending requests
        }
    except Exception as e:
        return {
            "active_sessions": 0,
            "otps": [],
            "pending_requests": 0,
            "error": str(e)
        }

# --- Session Generator Endpoints ---

class SessionStartRequest(BaseModel):
    phone_number: str

class SessionVerifyOTPRequest(BaseModel):
    session_id: str
    phone_number: str
    otp_code: str

class SessionVerify2FARequest(BaseModel):
    session_id: str
    password: str

@app.post("/admin/session/start")
async def start_session_generation(req: SessionStartRequest):
    """Start Telegram login and send OTP"""
    try:
        generator = get_session_generator()
        result = await generator.start_login(req.phone_number)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/admin/session/verify-otp")
async def verify_session_otp(req: SessionVerifyOTPRequest):
    """Verify OTP code and check for 2FA"""
    try:
        generator = get_session_generator()
        result = await generator.verify_otp(
            session_id=req.session_id,
            phone_number=req.phone_number,
            otp_code=req.otp_code
        )
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/admin/session/verify-2fa")
async def verify_session_2fa(req: SessionVerify2FARequest):
    """Verify 2FA password"""
    try:
        generator = get_session_generator()
        result = await generator.verify_2fa(req.session_id, req.password)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- Payment Settings Endpoints ---

@app.get("/admin/settings/payment")
async def get_payment_settings():
    """Get current UPI ID, QR Code URL, Channel Link, and Owner Username"""
    try:
        async with async_session() as session:
            # Fetch UPI ID
            upi_stmt = select(Settings).where(Settings.key == "payment_upi_id")
            upi_res = await session.execute(upi_stmt)
            upi_setting = upi_res.scalar_one_or_none()
            
            # Fetch QR Image URL
            qr_stmt = select(Settings).where(Settings.key == "payment_qr_image")
            qr_res = await session.execute(qr_stmt)
            qr_setting = qr_res.scalar_one_or_none()
            
            # Fetch Channel Link
            chan_stmt = select(Settings).where(Settings.key == "bot_channel_link")
            chan_res = await session.execute(chan_stmt)
            chan_setting = chan_res.scalar_one_or_none()
            
            # Fetch Owner Username
            owner_stmt = select(Settings).where(Settings.key == "bot_owner_username")
            owner_res = await session.execute(owner_stmt)
            owner_setting = owner_res.scalar_one_or_none()
            
            return {
                "upi_id": upi_setting.value if upi_setting else "",
                "qr_image": qr_setting.value if qr_setting else "",
                "channel_link": chan_setting.value if chan_setting else "",
                "owner_username": owner_setting.value if owner_setting else ""
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/settings/payment")
async def update_payment_settings(
    upi_id: str = Form(...),
    channel_link: str = Form(None),
    owner_username: str = Form(None),
    qr_image: UploadFile = File(None)
):
    """Update UPI ID, Channel Link, Owner, and optionally upload new QR Code"""
    try:
        # Validate and reject placeholder values
        PLACEHOLDER_CHANNELS = ["yourchannel", "@yourchannel", "your_channel"]
        PLACEHOLDER_OWNERS = ["@yourusername", "yourusername", "@your_username", "your_username"]
        
        if channel_link:
            channel_lower = channel_link.lower().strip()
            # Check if it's a placeholder
            if any(p in channel_lower for p in PLACEHOLDER_CHANNELS):
                raise HTTPException(
                    status_code=400, 
                    detail="❌ Please enter YOUR actual channel link, not the placeholder text!"
                )
            # Check if it's a valid URL
            if not channel_link.startswith("http"):
                raise HTTPException(
                    status_code=400,
                    detail="❌ Channel link must start with https://"
                )
        
        if owner_username:
            owner_lower = owner_username.lower().strip()
            # Check if it's a placeholder
            if any(p in owner_lower for p in PLACEHOLDER_OWNERS):
                raise HTTPException(
                    status_code=400,
                    detail="❌ Please enter YOUR actual username, not '@yourusername'!"
                )
            # Check if it starts with @
            if not owner_username.startswith("@"):
                raise HTTPException(
                    status_code=400,
                    detail="❌ Owner username must start with @"
                )
        
        async with async_session() as session:
            # Update UPI ID
            stmt = select(Settings).where(Settings.key == "payment_upi_id")
            res = await session.execute(stmt)
            setting = res.scalar_one_or_none()
            if not setting:
                session.add(Settings(key="payment_upi_id", value=upi_id))
            else:
                setting.value = upi_id
            
            # Update Channel Link (only if provided and valid)
            if channel_link:
                stmt = select(Settings).where(Settings.key == "bot_channel_link")
                res = await session.execute(stmt)
                setting = res.scalar_one_or_none()
                if not setting:
                    session.add(Settings(key="bot_channel_link", value=channel_link))
                else:
                    setting.value = channel_link
                logger.info(f"✅ Updated bot_channel_link to: {channel_link}")
            
            # Update Owner Username (only if provided and valid)
            if owner_username:
                stmt = select(Settings).where(Settings.key == "bot_owner_username")
                res = await session.execute(stmt)
                setting = res.scalar_one_or_none()
                if not setting:
                    session.add(Settings(key="bot_owner_username", value=owner_username))
                else:
                    setting.value = owner_username
                logger.info(f"✅ Updated bot_owner_username to: {owner_username}")
            
            # Handle QR Image Upload if provided
            if qr_image:
                print(f"Uploading new QR Code: {qr_image.filename}")
                content = await qr_image.read()
                
                # Upload to Supabase
                from supabase import create_client
                supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
                
                file_ext = qr_image.filename.split(".")[-1]
                file_path = f"payment_qr_{int(asyncio.get_event_loop().time())}.{file_ext}"
                bucket_name = "bot-uploads"
                
                try:
                    res = supabase.storage.from_(bucket_name).upload(
                        file_path, content, {"content-type": qr_image.content_type}
                    )
                    public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
                    print(f"QR Uploaded to: {public_url}")
                    
                    stmt = select(Settings).where(Settings.key == "payment_qr_image")
                    res = await session.execute(stmt)
                    setting = res.scalar_one_or_none()
                    if not setting:
                        session.add(Settings(key="payment_qr_image", value=public_url))
                    else:
                        setting.value = public_url
                        
                except Exception as upload_err:
                    print(f"Upload Error: {upload_err}")
                    # Don't crash full request if upload fails, but log it
                    pass

            await session.commit()
            return {"success": True, "message": "Settings updated successfully"}
            
    except Exception as e:
        print(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/deposits/enhanced")
async def get_deposits_enhanced():
    async with async_session() as session:
        # Join with User to get username/id
        from sqlalchemy.orm import joinedload
        result = await session.execute(
            select(Deposit).options(joinedload(Deposit.user)).order_by(Deposit.created_at.desc())
        )
        deposits = result.scalars().all()
        return [
            {
                "id": d.id,
                "amount": d.amount,
                "upi_ref_id": d.upi_ref_id,
                "screenshot_path": d.screenshot_path,
                "status": d.status,
                "created_at": d.created_at,
                "user": {
                    "id": d.user.id,
                    "telegram_id": d.user.telegram_id,
                    "username": d.user.username,
                    "full_name": d.user.full_name
                }
            }
            for d in deposits
        ]

# --- Serve Frontend ---
dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # API routes are NOT caught here by default if they match specifically
    # But we want to ensure any non-api/non-admin-api route serves index.html
    if full_path.startswith("admin/"): # This matches frontend routes like /admin/users
        index_file = os.path.join(dist_path, "index.html")
        return FileResponse(index_file)
    
    # Static files check
    file_path = os.path.join(dist_path, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # Root or other SPA routes
    index_file = os.path.join(dist_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    
    return {"error": "Frontend not found"}

if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")

# Mount uploads directory for payment screenshots
uploads_path = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")
"""

Add Account Creation Endpoint

This creates the missing /admin/accounts POST endpoint

"""



# Add this code to backend/main.py



from pydantic import BaseModel



class AccountCreate(BaseModel):

    country_id: int

    phone_number: str

    session_data: str

    type: str = "ID"

    twofa_password: str = None



@app.post("/admin/accounts")

async def create_account(account: AccountCreate):

    """Create a new account - allows duplicates after sold"""

    async with async_session() as session:

        # Create new account (no duplicate check - allows restocking)

        new_account = Account(

            country_id=account.country_id,

            phone_number=account.phone_number,

            session_data=account.session_data,

            type=account.type,

            twofa_password=account.twofa_password,

            is_sold=False

        )

        

        session.add(new_account)

        await session.commit()

        await session.refresh(new_account)

        

        return {

            "success": True,

            "message": "Account added successfully",

            "account": {

                "id": new_account.id,

                "phone_number": new_account.phone_number,

                "country_id": new_account.country_id

            }

        }

