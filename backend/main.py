from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import init_db, async_session
from .bot import bot, dp
from .models import User, Country, Account, Purchase, Deposit, Settings
from .session_manager import get_session_manager
from .session_generator_service import get_session_generator
from sqlalchemy import select, update, delete
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import os
from fastapi import UploadFile, File, Form

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
# BASE_URL from env var (for Railway/Render), default to actual Koyeb URL if missing
# This is the PERMANENT FIX ensuring webhook is always set correct on boot
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL", "https://shallow-reggie-telegrambotmine-8d891f24.koyeb.app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    await init_db()
    
    # Set Webhook on Startup
    # Set Webhook on Startup
    webhook_url = f"{BASE_WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    print(f"🔄 Setting webhook to: {webhook_url}", flush=True)
    
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True
    )
    
    # Verify Webhook
    info = await bot.get_webhook_info()
    print(f"✅ Webhook Info: URL={info.url} | Custom Cert={info.has_custom_certificate} | Pending={info.pending_update_count}", flush=True)
    
    yield
    
    # Delete Webhook on Shutdown
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health_check():
    return {"status": "ok", "mode": "webhook", "service": "Telegram Bot Backend"}

@app.get("/health")
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

@app.post("/admin/login")
async def admin_login(req: LoginRequest):
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
    print(f"🔐 Login Attempt: Input='{req.password}' | Env='{admin_pass}'") # DEBUG LOG
    if req.password.strip() == admin_pass.strip():
        return {"status": "success", "token": "admin_token"} # Simple token for now
    print("❌ Password mismatch")
    raise HTTPException(status_code=401, detail="Invalid password")

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
    async with async_session() as session:
        # Total Users
        users_stmt = select(User)
        users_res = await session.execute(users_stmt)
        total_users = len(users_res.scalars().all())
        
        # Total Sales (sum of all purchases)
        purchases_stmt = select(Purchase.amount)
        purchases_res = await session.execute(purchases_stmt)
        total_sales = sum(purchases_res.scalars().all())
        
        # Pending Deposits
        pending_stmt = select(Deposit).where(Deposit.status == "PENDING")
        pending_res = await session.execute(pending_stmt)
        pending_deposits = len(pending_res.scalars().all())
        
        return {
            "total_users": total_users,
            "total_sales": total_sales,
            "pending_deposits": pending_deposits
        }

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
    """Get current UPI ID and QR Code URL"""
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
            
            return {
                "upi_id": upi_setting.value if upi_setting else "",
                "qr_image": qr_setting.value if qr_setting else ""
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/settings/payment")
async def update_payment_settings(
    upi_id: str = Form(...),
    qr_image: UploadFile = File(None)
):
    """Update UPI ID and optionally upload new QR Code"""
    try:
        async with async_session() as session:
            # Update UPI ID
            upi_stmt = select(Settings).where(Settings.key == "payment_upi_id")
            upi_res = await session.execute(upi_stmt)
            upi_setting = upi_res.scalar_one_or_none()
            
            if not upi_setting:
                upi_setting = Settings(key="payment_upi_id", value=upi_id)
                session.add(upi_setting)
            else:
                upi_setting.value = upi_id
            
            # Handle QR Image Upload if provided
            if qr_image:
                print(f"Uploading new QR Code: {qr_image.filename}")
                content = await qr_image.read()
                
                # Upload to Supabase
                from supabase import create_client
                supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
                
                file_ext = qr_image.filename.split(".")[-1]
                file_path = f"payment_qr_{int(asyncio.get_event_loop().time())}.{file_ext}"
                
                # Ensure bucket exists (created in task plan)
                bucket_name = "bot-uploads"
                
                try:
                    res = supabase.storage.from_(bucket_name).upload(
                        file_path,
                        content,
                        {"content-type": qr_image.content_type}
                    )
                    
                    # Get Public URL
                    public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
                    print(f"QR Uploaded to: {public_url}")
                    
                    # Update DB
                    qr_stmt = select(Settings).where(Settings.key == "payment_qr_image")
                    qr_res = await session.execute(qr_stmt)
                    qr_setting = qr_res.scalar_one_or_none()
                    
                    if not qr_setting:
                        qr_setting = Settings(key="payment_qr_image", value=public_url)
                        session.add(qr_setting)
                    else:
                        qr_setting.value = public_url
                        
                except Exception as upload_err:
                    print(f"Upload Error: {upload_err}")
                    raise HTTPException(status_code=500, detail=f"Failed to upload QR: {upload_err}")

            await session.commit()
            return {"success": True, "message": "Payment settings updated"}
            
    except Exception as e:
        print(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Settings API ---

class PaymentSettings(BaseModel):
    upi_id: str

@app.get("/admin/settings/payment")
async def get_payment_settings():
    async with async_session() as session:
        # Fetch UPI ID
        res_upi = await session.execute(select(Settings).where(Settings.key == "payment_upi_id"))
        upi_setting = res_upi.scalar_one_or_none()
        
        # Fetch QR Image Path
        res_qr = await session.execute(select(Settings).where(Settings.key == "payment_qr_image"))
        qr_setting = res_qr.scalar_one_or_none()
        
        return {
            "upi_id": upi_setting.value if upi_setting else "",
            "qr_image": qr_setting.value if qr_setting else None
        }

@app.post("/admin/settings/payment")
async def update_payment_settings(settings: PaymentSettings):
    async with async_session() as session:
        # Upsert UPI ID
        stmt = select(Settings).where(Settings.key == "payment_upi_id")
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = settings.upi_id
        else:
            session.add(Settings(key="payment_upi_id", value=settings.upi_id))
            
        await session.commit()
        return {"success": True}

from fastapi import UploadFile, File

@app.post("/admin/settings/qr")
async def upload_payment_qr(file: UploadFile = File(...)):
    try:
        file_ext = file.filename.split('.')[-1]
        save_path = f"uploads/payment_qr.{file_ext}"
        os.makedirs("uploads", exist_ok=True)
        
        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        # Update DB
        async with async_session() as session:
            stmt = select(Settings).where(Settings.key == "payment_qr_image")
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.value = save_path
            else:
                session.add(Settings(key="payment_qr_image", value=save_path))
            await session.commit()
            
        return {"success": True, "path": save_path}
    except Exception as e:
        return {"success": False, "message": str(e)}

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
