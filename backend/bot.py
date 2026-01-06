import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from .database import async_session
from .models import User, Country, Account, Purchase, Deposit, Settings
from .session_manager import get_session_manager
from .device_manager import DeviceManager
from sqlalchemy import select, update

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Global Error Handler for Maximum Stability ---
@dp.errors()
async def error_handler(event, exception):
    """
    Global error handler to prevent bot crashes.
    Catches all uncaught exceptions and logs them instead of crashing.
    """
    logger.error(f"❌ Uncaught error in {event.__class__.__name__}: {exception}", exc_info=True)
    
    # Try to notify user of error if it's a callback or message update
    try:
        if hasattr(event, 'update') and event.update:
            update = event.update
            
            # Try to send error message to user
            chat_id = None
            if update.message:
                chat_id = update.message.chat.id
            elif update.callback_query:
                chat_id = update.callback_query.message.chat.id
            
            if chat_id:
                try:
                    await bot.send_message(
                        chat_id,
                        "⚠️ An error occurred. Please try again or contact support if the issue persists.",
                        reply_markup=get_back_to_main()
                    )
                except:
                    pass  # If we can't send the message, just log it
    except Exception as e:
        logger.error(f"Error in error handler: {e}")
    
    # Return True to mark error as handled and prevent bot crash
    return True

# --- FSM States ---
class DepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_utr = State()
    confirming_utr = State()
    waiting_for_screenshot = State()
    confirming_screenshot = State()

# --- Keyboards ---

def get_main_menu(is_admin=False):
    builder = InlineKeyboardBuilder()
    
    # Row 1: Get Account | Profile
    builder.row(
        InlineKeyboardButton(text="🟢 Get Account", callback_data="btn_accounts"),
        InlineKeyboardButton(text="👤 Profile", callback_data="btn_profile")
    )
    
    # Row 2: Deposit | Support
    builder.row(
        InlineKeyboardButton(text="💰 Deposit", callback_data="btn_deposit"),
        InlineKeyboardButton(text="🆘 Support", callback_data="btn_help")
    )
    
    # Row 4: Main Menu
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
    
    if is_admin:
        admin_url = os.getenv("ADMIN_WEBAPP_URL", "https://telegram-bot-full.vercel.app")
        builder.row(
            InlineKeyboardButton(text="⚙️ Admin Web App", web_app=WebAppInfo(url=admin_url)),
            InlineKeyboardButton(text="💳 Payment Settings", web_app=WebAppInfo(url=admin_url + "/settings"))
        )
    
    return builder.as_markup()

def get_back_to_main():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
    return builder.as_markup()

# --- Handlers ---

@dp.startup()
async def on_startup():
    logger.info("Bot started and polling...")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Received /start from {message.from_user.id}")
    is_admin = False
    try:
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == message.from_user.id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            # Check if this telegram ID should be admin
            # Check if this telegram ID should be admin
            admin_telegram_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
            user_id_str = str(message.from_user.id)
            should_be_admin = admin_telegram_id and user_id_str == admin_telegram_id
            
            logger.info(f"Start Check: User={user_id_str}, AdminEnv={admin_telegram_id}, Match={should_be_admin}")

            if not user:
                user = User(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    is_admin=should_be_admin
                )
                session.add(user)
            elif user.is_admin != should_be_admin:
                # Update admin status if changed
                user.is_admin = should_be_admin
                
            await session.commit()
            is_admin = user.is_admin
            
    except Exception as e:
        logger.error(f"Error in /start handler: {e}")
        # DEBUG: Tell the user what happened so we can diagnose "no reply" issues
        if should_be_admin: # Only show details to admin if possible, or just show everyone for now
             await message.answer(f"⚠️ <b>System Error during Login:</b>\n<code>{str(e)}</code>", parse_mode="HTML")
        # Even if DB fails, we want to try show the menu if possible, or maybe stop here?
    
    # Ensure is_admin has a value even if DB failed (False)
    # If DB failed, this might fail too if get_main_menu relies on DB? No it doesn't.
    try:
        await message.answer(
            f"<b>👋 Hello {message.from_user.full_name}, Welcome to our Premium Store!</b>\n\n"
        "⚡ <b>Instant Delivery | High Quality | 24/7 Support</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛒 <b>Best Place to Buy:</b>\n"
        "• Telegram Accounts (TData/Session)\n"
        "• Fresh & Aged IDs\n"
        "• Bulk Orders Available\n\n"
        "👇 <b>Choose an option below to start:</b>",
        reply_markup=get_main_menu(is_admin=is_admin),
        parse_mode="HTML"
    )
    except Exception as e:
        logger.error(f"Error sending start message: {e}")
        # Fallback response if main message fails
        try:
            await message.answer("Welcome! The bot is ready. Type /start to begin.")
        except Exception:
            pass  # If even fallback fails, log it but don't crash

@dp.callback_query(F.data == "btn_deposit")
async def process_deposit_start(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇮🇳 UPI (Manual)", callback_data="btn_deposit_upi_manual"))
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
    
    await callback.message.edit_text(
        "<b>💸 Deposit Funds</b>\n\n"
        "Choose your deposit method:\n\n"
        "• <b>UPI (Manual)</b> — Admin verifies your UTR before credit",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "btn_deposit_upi_manual")
async def process_deposit_method_upi(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_amount)
    await callback.message.edit_text(
        "<b>💎 Deposit Balance</b>\n\n"
        "Please enter the amount in <b>₹ (INR)</b> you wish to deposit:",
        reply_markup=get_back_to_main(),
        parse_mode="HTML"
    )

@dp.message(DepositStates.waiting_for_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("❌ <b>Invalid Amount!</b> Please enter a numeric value:")
        return
    
    amount = float(message.text)
    await state.update_data(deposit_amount=amount)
    await state.set_state(DepositStates.waiting_for_utr)
    
    async with async_session() as session:
        # Fetch Payment Settings
        upi_res = await session.execute(select(Settings).where(Settings.key == "payment_upi_id"))
        qr_res = await session.execute(select(Settings).where(Settings.key == "payment_qr_image"))
        
        upi_id = upi_res.scalar_one_or_none()
        qr_image = qr_res.scalar_one_or_none()
        
        target_upi_id = upi_id.value if upi_id else "example@upi"
        
        # Check if custom QR image exists
        custom_qr_path = qr_image.value if qr_image else None
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
        
        if custom_qr_path:
            # Check if it's a URL (Supabase) or Local File
            photo_input = None
            if custom_qr_path.startswith("http"):
                photo_input = custom_qr_path
            elif os.path.exists(custom_qr_path):
                photo_input = FSInputFile(custom_qr_path)
            
            if photo_input:
                # Send Custom QR
                text = (
                    f"<b>🏧 Deposit Amount: ₹{amount}</b>\n\n"
                    f"📍 <b>UPI ID:</b> <code>{target_upi_id}</code>\n\n"
                    "📸 <b>Scan the QR Code below to Pay</b>\n\n"
                    "✅ <b>Instructions:</b>\n"
                    "1. Open your UPI app.\n"
                    "2. Scan this QR or pay to the UPI ID.\n"
                    "3. Copy the <b>UTR / Transaction Ref ID</b>.\n\n"
                    "👉 <b>Please enter the UTR / Ref ID here after payment:</b>"
                )
                await message.answer_photo(
                    photo_input,
                    caption=text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
            else:
                 # Fallback if file not found
                 pass # Fall through to dynamic generation logic below? No, duplicate logic.
                 # Let's restructure properly
        
        # If no custom QR or failed path, generate dynamic one
        if not custom_qr_path or (not photo_input):
            # Generate Dynamic QR
            qr_data = f"upi://pay?pa={target_upi_id}&am={amount}&cu=INR&tn=Deposit"
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_data}"

            text = (
                f"<b>🏧 Deposit Amount: ₹{amount}</b>\n\n"
                f"📍 <b>UPI ID:</b> <code>{target_upi_id}</code>\n\n"
                "📸 <b>Scan QR or use the UPI ID above</b>\n\n"
                "✅ <b>Instructions:</b>\n"
                "1. Open your UPI app (PhonePe, GPay, Paytm, etc.)\n"
                "2. Pay the above amount.\n"
                "3. Copy the <b>UTR / Transaction Ref ID</b>.\n\n"
                "👉 <b>Please enter the UTR / Ref ID here after payment:</b>"
            )
            
            await message.answer_photo(
                qr_url,
                caption=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )

@dp.message(DepositStates.waiting_for_utr)
async def process_deposit_utr(message: types.Message, state: FSMContext):
    utr_id = message.text
    if not utr_id or len(utr_id) < 6:
        await message.answer("❌ <b>Invalid UTR!</b>\n\nPlease enter a valid Transaction Ref ID:", reply_markup=get_back_to_main(), parse_mode="HTML")
        return
    
    # Check for duplicate UTR
    async with async_session() as session:
        stmt = select(Deposit).where(Deposit.upi_ref_id == utr_id)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        
        if existing:
            await message.answer(
                "⚠️ <b>Duplicate UTR Detected!</b>\n\n"
                "This Transaction Ref ID has already been submitted. Please do not submit double UTRs. "
                "If you believe this is an error, please contact support.",
                reply_markup=get_back_to_main(),
                parse_mode="HTML"
            )
            return

    await state.update_data(utr_id=utr_id)
    await state.set_state(DepositStates.confirming_utr)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Confirm UTR", callback_data="confirm_utr"))
    builder.row(InlineKeyboardButton(text="❌ Edit UTR", callback_data="btn_deposit_reenter_amount")) # Simplified backtrack
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))

    await message.answer(
        f"🔎 <b>Review your UTR:</b>\n\n"
        f"<code>{utr_id}</code>\n\n"
        "Is this correct? Click confirm to proceed to the final step.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "confirm_utr", DepositStates.confirming_utr)
async def process_utr_confirmed(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_screenshot)
    await callback.message.edit_text(
        "✅ <b>UTR Confirmed!</b>\n\n"
        "📸 <b>Final Step:</b> Please upload the <b>Payment Screenshot</b> for verification:",
        reply_markup=get_back_to_main(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "btn_deposit_reenter_amount", DepositStates.confirming_utr)
async def process_reenter_utr(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_utr)
    await callback.message.edit_text(
        "📝 <b>Re-enter UTR:</b>\n\nPlease send the correct Transaction Ref ID now:",
        reply_markup=get_back_to_main(),
        parse_mode="HTML"
    )

@dp.message(DepositStates.waiting_for_screenshot, F.photo)
async def process_deposit_screenshot(message: types.Message, state: FSMContext):
    # Save photo temporarily in state data instead of file immediately to allow confirmation
    photo = message.photo[-1]
    await state.update_data(temp_photo_id=photo.file_id)
    await state.set_state(DepositStates.confirming_screenshot)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Confirm & Submit", callback_data="confirm_deposit"))
    builder.row(InlineKeyboardButton(text="❌ Re-upload Photo", callback_data="reupload_screenshot"))
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))

    await message.answer(
        "🔎 <b>Is this the correct payment screenshot?</b>\n\n"
        "Click the button below to submit your deposit for admin approval.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "reupload_screenshot", DepositStates.confirming_screenshot)
async def process_reupload_screenshot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_screenshot)
    await callback.message.edit_text(
        "📸 <b>Please upload the screenshot again:</b>",
        reply_markup=get_back_to_main(),
        parse_mode="HTML"
    )

from supabase import create_client, Client
import os

# Initialize Supabase Client
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@dp.callback_query(F.data == "confirm_deposit", DepositStates.confirming_screenshot)
async def process_deposit_final_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("deposit_amount")
    utr_id = data.get("deposit_utr")
    photo_id = data.get("temp_photo_id")
    
    # Download photo from Telegram
    file_info = await bot.get_file(photo_id)
    file_ext = file_info.file_path.split('.')[-1]
    
    # Create unique filename
    timestamp = int(asyncio.get_event_loop().time())
    file_name = f"deposit_{callback.from_user.id}_{timestamp}.{file_ext}"
    
    # Download file to memory/temp buffer
    downloaded_file = await bot.download_file(file_info.file_path)
    # downloaded_file is a BytesIO object. read() might handle it if seek is at 0, 
    # but to be safe with io.BytesIO from aiogram, we use getvalue() or seek(0)
    if hasattr(downloaded_file, 'getvalue'):
        file_bytes = downloaded_file.getvalue()
    else:
        # Fallback if it's a different stream type
        downloaded_file.seek(0)
        file_bytes = downloaded_file.read()

    try:
        # Upload to Supabase Storage
        bucket_name = "bot-uploads"
        # Content type is guessed by extension usually, but we can be explicit if needed
        res = supabase.storage.from_(bucket_name).upload(
            file_name,
            file_bytes,
            {"content-type": f"image/{file_ext}"}
        )
        
        # Get Public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        
        async with async_session() as session:
            # Get user
            stmt = select(User).where(User.telegram_id == callback.from_user.id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if user:
                deposit = Deposit(
                    user_id=user.id,
                    amount=amount,
                    upi_ref_id=utr_id,
                    screenshot_path=public_url, # Save full URL
                    status="PENDING"
                )
                session.add(deposit)
                await session.commit()
                
                # Notify User
                await callback.message.edit_text(
                    "✅ <b>Deposit Submitted!</b>\n\n"
                    f"💰 Amount: ₹{amount}\n"
                    f"🆔 UTR: <code>{utr_id}</code>\n\n"
                    "⏳ Your deposit is pending verification. Please wait for admin approval.",
                    reply_markup=get_back_to_main(),
                    parse_mode="HTML"
                )
                
                # Notify Admin
                admin_id = os.getenv("ADMIN_TELEGRAM_ID")
                if admin_id:
                    try:
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=photo_id,
                            caption=(
                                f"🔔 <b>New Deposit Alert!</b>\n\n"
                                f"👤 User: {callback.from_user.full_name} (@{callback.from_user.username})\n"
                                f"💰 Amount: ₹{amount}\n"
                                f"🆔 UTR: {utr_id}\n"
                                f"🖼 URL: {public_url}"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify admin: {e}")
            else:
                 await callback.message.edit_text("❌ User not found in database.")
                 
    except Exception as e:
        logger.error(f"Failed to upload to Supabase: {e}")
        await callback.message.answer(f"❌ Error uploading screenshot: {e}")

    await state.clear()

@dp.message(DepositStates.waiting_for_screenshot)
async def process_deposit_screenshot_invalid(message: types.Message):
    await message.answer(
        "⚠️ <b>Not a picture or anything! Only images are allowed.</b>\n\n"
        "Please upload the payment screenshot to proceed:",
        reply_markup=get_back_to_main(),
        parse_mode="HTML"
    )



@dp.callback_query(F.data == "btn_accounts")
async def process_accounts(callback: types.CallbackQuery):
    async with async_session() as session:
        # Get all countries
        stmt = select(Country)
        result = await session.execute(stmt)
        countries = result.scalars().all()
        
        # Calculate stock for each country (only IDs)
        countries_with_stock = []
        for country in countries:
            stock_stmt = select(Account).where(
                Account.country_id == country.id,
                Account.is_sold == False,
                Account.type == "ID"
            )
            stock_res = await session.execute(stock_stmt)
            stock_count = len(stock_res.scalars().all())
            
            # Only include countries with available stock
            if stock_count > 0:
                countries_with_stock.append({
                    'country': country,
                    'stock': stock_count
                })

    if not countries_with_stock:
        await callback.message.edit_text(
            "❌ <b>No accounts available at the moment.</b>\n\n"
            "Please check back later or contact support.",
            reply_markup=get_back_to_main(),
            parse_mode="HTML"
        )
        return

    builder = InlineKeyboardBuilder()
    for item in countries_with_stock:
        country = item['country']
        stock = item['stock']
        button_text = f"{country.emoji} {country.name} | 📦 {stock} IDs"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"country_{country.id}"))
    
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
    
    await callback.message.edit_text(
        "🛍️ <b>Select a country to buy IDs:</b>\n\n"
        "Only showing countries with available stock.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("country_"))
async def process_country_selection(callback: types.CallbackQuery):
    country_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        stmt = select(Country).where(Country.id == country_id)
        result = await session.execute(stmt)
        country = result.scalar_one_or_none()

        if not country:
            await callback.answer("Country not found.")
            return

        # Count available stock for IDs
        stock_stmt = select(Account).where(
            Account.country_id == country_id,
            Account.is_sold == False,
            Account.type == "ID"
        )
        stock_res = await session.execute(stock_stmt)
        available_accounts = stock_res.scalars().all()
        available_stock = len(available_accounts)

        if available_stock == 0:
            text = f"🏴 <b>Country:</b> {country.emoji} {country.name}\n"
            text += f"💵 <b>Price per ID:</b> ₹{country.price}\n"
            text += f"📦 <b>Available Stock:</b> {available_stock} IDs\n\n"
            text += "❌ Out of stock. Please check back later."
            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="btn_accounts"))
            builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
            
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            return

        # Get first available account to show phone number
        preview_account = available_accounts[0]
        
        # Show confirmation with phone number and disclaimer
        text = f"🏴 <b>Country:</b> {country.emoji} {country.name}\n"
        text += f"💵 <b>Price:</b> ₹{country.price}\n"
        text += f"📱 <b>Phone Number:</b> <code>{preview_account.phone_number}</code>\n"
        text += f"📦 <b>Stock:</b> {available_stock} available\n\n"
        text += "⚠️ <b>IMPORTANT DISCLAIMER:</b>\n"
        text += "• We are NOT responsible for banned/frozen accounts\n"
        text += "• No refunds for account restrictions\n"
        text += "• Use at your own risk\n"
        text += "• Follow Telegram's Terms of Service\n\n"
        text += "💡 <b>You will receive:</b>\n"
        text += "• Phone number\n"
        text += "• OTP codes automatically\n"
        text += "• Login assistance\n\n"
        text += "✅ <b>Confirm purchase?</b>"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅ Confirm Purchase",
            callback_data=f"confirm_buy_{country_id}"
        ))
        builder.row(InlineKeyboardButton(
            text="❌ Cancel",
            callback_data="btn_accounts"
        ))
        builder.row(InlineKeyboardButton(
            text="🏠 Main Menu",
            callback_data="btn_main_menu"
        ))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "btn_profile")
async def process_profile(callback: types.CallbackQuery):
    async with async_session() as session:
        # Get user details
        stmt = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("User not found.")
            return

        # Calculate Total Spent
        spent_stmt = select(Purchase.amount).where(Purchase.user_id == user.id)
        spent_res = await session.execute(spent_stmt)
        total_spent = sum(spent_res.scalars().all())

        # Calculate Ranking (all users sum of purchases)
        all_users_stmt = select(User.id)
        all_users_res = await session.execute(all_users_stmt)
        all_user_ids = all_users_res.scalars().all()

        rankings = []
        for uid in all_user_ids:
            u_spent_stmt = select(Purchase.amount).where(Purchase.user_id == uid)
            u_spent_res = await session.execute(u_spent_stmt)
            rankings.append((uid, sum(u_spent_res.scalars().all())))
        
        # Sort rankings descending
        rankings.sort(key=lambda x: x[1], reverse=True)
        user_rank = next((i + 1 for i, r in enumerate(rankings) if r[0] == user.id), "N/A")

        text = "👤 <b>Your Profile</b>\n\n"
        text += f"ID: <code>{user.telegram_id}</code>\n"
        text += f"Name: {user.full_name}\n"
        text += f"Username: @{user.username if user.username else 'N/A'}\n"
        text += f"💰 Balance: <b>₹{user.balance}</b>\n"
        text += f"💸 Total Spent: <b>₹{total_spent}</b>\n"
        text += f"🏆 Rank: <b>#{user_rank}</b> in total buyers\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📜 Transaction Deposits", callback_data="btn_transactions"))
        builder.row(InlineKeyboardButton(text="🛒 ID Buyed", callback_data="btn_purchases"))
        builder.row(InlineKeyboardButton(text="➕ Add Balance", callback_data="btn_deposit"))
        builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "btn_transactions")
async def process_transactions_history(callback: types.CallbackQuery):
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == callback.from_user.id)
        u_res = await session.execute(stmt)
        user = u_res.scalar_one_or_none()
        
        if not user: return
        
        dep_stmt = select(Deposit).where(Deposit.user_id == user.id).order_by(Deposit.created_at.desc()).limit(10)
        dep_res = await session.execute(dep_stmt)
        deposits = dep_res.scalars().all()
        
    text = "📜 <b>Recent Deposits</b>\n\n"
    if not deposits:
        text += "<i>No deposits found.</i>"
    else:
        for d in deposits:
            status_emo = "⏳" if d.status == "PENDING" else "✅" if d.status == "APPROVED" else "❌"
            text += f"{status_emo} ₹{d.amount} | {d.created_at.strftime('%Y-%m-%d')}\n"
            text += f"Ref: <code>{d.upi_ref_id}</code>\n\n"
            
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Profile", callback_data="btn_profile"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "btn_purchases")
async def process_purchase_history(callback: types.CallbackQuery):
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == callback.from_user.id)
        u_res = await session.execute(stmt)
        user = u_res.scalar_one_or_none()
        
        if not user: return
        
        pur_stmt = select(Purchase).where(Purchase.user_id == user.id).order_by(Purchase.created_at.desc()).limit(10)
        pur_res = await session.execute(pur_stmt)
        purchases = pur_res.scalars().all()
        
    # Show purchase history as clickable buttons
    text = "🛒 <b>Purchase History</b>\nSelect an account to manage sessions:\n\n"
    builder = InlineKeyboardBuilder()
    
    if not purchases:
        text = "🛒 <b>Purchase History</b>\n\n<i>No purchases found.</i>"
    else:
        for p in purchases:
            # Use purchase ID for management
            label = f"📱 Account #{p.id} | ₹{p.amount}"
            builder.row(InlineKeyboardButton(
                text=f"{label} | {p.created_at.strftime('%Y-%m-%d')}",
                callback_data=f"manage_sess_{p.id}"
            ))
        
    builder.row(InlineKeyboardButton(text="🔙 Back to Profile", callback_data="btn_profile"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "btn_help")
async def process_help(callback: types.CallbackQuery):
    text = (
        "<b>❓ Need Help?</b>\n\n"
        "⚡ <b>We have the fastest customer support!</b>\n\n"
        "If you have any issues with your purchase or deposit, "
        "feel free to contact us. Our team is online 24/7."
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Our Channel", url="https://t.me/YourChannel"))
    builder.row(InlineKeyboardButton(text="👨‍💻 Bot Owner", url="https://t.me/YourSupportUser"))
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "btn_main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    # Clear any FSM state
    await state.clear()
    
    # Check if user is admin
    is_admin = False
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            is_admin = user.is_admin
            
    # FORCE Admin Check from Env Var (Fixes "Missing Admin Panel" bug)
    admin_telegram_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    user_id_str = str(callback.from_user.id)
    
    logger.info(f"Menu Check: User={user_id_str}, AdminEnv={admin_telegram_id}")
    
    if admin_telegram_id and user_id_str == admin_telegram_id:
        is_admin = True
    
    # If message has photo (like QR code), delete it and send new message
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            f"<b><i>Welcome back! 🌟</i></b>\n\n"
            "💠 <b>Select an option below:</b>",
            reply_markup=get_main_menu(is_admin=is_admin),
            parse_mode="HTML"
        )
    else:
        # Regular text message, can edit
        await callback.message.edit_text(
            f"<b><i>Welcome back! 🌟</i></b>\n\n"
            "💠 <b>Select an option below:</b>",
            reply_markup=get_main_menu(is_admin=is_admin),
            parse_mode="HTML"
        )


@dp.callback_query(F.data.startswith("buy_id_"))
async def process_buy_id(callback: types.CallbackQuery):
    country_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        # Get user
        stmt = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        # Get country
        stmt = select(Country).where(Country.id == country_id)
        result = await session.execute(stmt)
        country = result.scalar_one_or_none()

        if not user or not country:
            await callback.answer("Error: User or Country not found.")
            return

        if user.balance < country.price:
            await callback.answer(f"Insufficient balance. You need ₹{country.price - user.balance} more.", show_alert=True)
            return

        # Find available account
        stmt = select(Account).where(Account.country_id == country_id, Account.is_sold == False, Account.type == "ID").limit(1)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            await callback.answer("Out of stock for this country.", show_alert=True)
            return

        # Process purchase
        user.balance -= country.price
        account.is_sold = True
        
        purchase = Purchase(
            user_id=user.id,
            account_id=account.id,
            amount=country.price
        )
        session.add(purchase)
        await session.commit()

        await callback.message.answer(
            f"✅ <b>Purchase Successful!</b>\n\n"
            f"📱 Phone: <code>{account.phone_number}</code>\n"
            f"🔑 Session Data: <code>{account.session_data}</code>\n\n"
            "<i>Keep this safe!</i>",
            parse_mode="HTML"
        )
        await callback.answer("Success!")

@dp.message()
async def catch_all_handler(message: types.Message):
    await message.answer(
        "⚠️ <b>Please start the bot first!</b>\n"
        "Use the <b>/start</b> command to access the menu.",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "btn_sessions")
async def process_sessions(callback: types.CallbackQuery):
    async with async_session() as session:
        # Get all countries
        stmt = select(Country)
        result = await session.execute(stmt)
        countries = result.scalars().all()
        
        # Calculate stock for each country (only Sessions)
        countries_with_stock = []
        for country in countries:
            stock_stmt = select(Account).where(
                Account.country_id == country.id,
                Account.is_sold == False,
                Account.type == "Session"
            )
            stock_res = await session.execute(stock_stmt)
            stock_count = len(stock_res.scalars().all())
            
            # Only include countries with available stock
            if stock_count > 0:
                countries_with_stock.append({
                    'country': country,
                    'stock': stock_count
                })

    if not countries_with_stock:
        await callback.message.edit_text(
            "❌ <b>No sessions available at the moment.</b>\n\n"
            "Please check back later or contact support.",
            reply_markup=get_back_to_main(),
            parse_mode="HTML"
        )
        return

    builder = InlineKeyboardBuilder()
    for item in countries_with_stock:
        country = item['country']
        stock = item['stock']
        button_text = f"{country.emoji} {country.name} | 📦 {stock} Sessions"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"session_{country.id}"))
    
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
    
    await callback.message.edit_text(
        "📱 <b>Select a country to buy Sessions:</b>\n\n"
        "Only showing countries with available stock.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("session_"))
async def process_session_country(callback: types.CallbackQuery):
    country_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        stmt = select(Country).where(Country.id == country_id)
        result = await session.execute(stmt)
        country = result.scalar_one_or_none()

        if not country:
            await callback.answer("Country not found.")
            return

        # Count available stock for Sessions
        stock_stmt = select(Account).where(
            Account.country_id == country_id,
            Account.is_sold == False,
            Account.type == "Session"
        )
        stock_res = await session.execute(stock_stmt)
        available_stock = len(stock_res.scalars().all())

        # Show price, stock, and buy button
        text = f"🏴 <b>Country (Session):</b> {country.emoji} {country.name}\n"
        text += f"💵 <b>Price per Session:</b> ₹{country.price}\n"
        text += f"📦 <b>Available Stock:</b> {available_stock} Sessions\n\n"
        
        if available_stock > 0:
            text += "✅ Click below to purchase session."
        else:
            text += "❌ Out of stock. Please check back later."
        
        builder = InlineKeyboardBuilder()
        if available_stock > 0:
            builder.row(InlineKeyboardButton(text="🛒 Buy Session", callback_data=f"buy_sess_{country.id}"))
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="btn_sessions"))
        builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- Purchase Confirmation Handler ---

@dp.callback_query(F.data.startswith("confirm_buy_"))
async def process_confirm_purchase(callback: types.CallbackQuery):
    """Process purchase after user confirms"""
    country_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        # Get user
        user_stmt = select(User).where(User.telegram_id == callback.from_user.id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        # Get country
        country_stmt = select(Country).where(Country.id == country_id)
        country_res = await session.execute(country_stmt)
        country = country_res.scalar_one_or_none()
        
        if not user or not country:
            await callback.answer("Error: User or country not found")
            return
        
        # Check if user has sufficient balance
        if user.balance < country.price:
            await callback.message.edit_text(
                f"❌ <b>Insufficient Balance!</b>\n\n"
                f"💰 Your Balance: ₹{user.balance}\n"
                f"💵 Required: ₹{country.price}\n"
                f"💸 Short by: ₹{country.price - user.balance}\n\n"
                "Please deposit to continue.",
                reply_markup=InlineKeyboardBuilder()
                    .row(InlineKeyboardButton(text="💰 Deposit", callback_data="btn_deposit"))
                    .row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
                    .as_markup(),
                parse_mode="HTML"
            )
            return
        
        # Find available account
        account_stmt = select(Account).where(
            Account.country_id == country_id,
            Account.is_sold == False,
            Account.type == "ID"
        ).limit(1)
        account_res = await session.execute(account_stmt)
        account = account_res.scalar_one_or_none()
        
        if not account:
            await callback.message.edit_text(
                "❌ <b>Out of Stock!</b>\n\n"
                f"Sorry, no {country.name} IDs available right now.",
                reply_markup=InlineKeyboardBuilder()
                    .row(InlineKeyboardButton(text="🔙 Back", callback_data="btn_accounts"))
                    .as_markup(),
                parse_mode="HTML"
            )
            return
        
        # Process purchase
        user.balance -= country.price
        account.is_sold = True
        
        purchase = Purchase(
            user_id=user.id,
            account_id=account.id,
            amount=country.price
        )
        session.add(purchase)
        await session.commit()
        await session.refresh(purchase)
        
        # Show purchase success with OTP button
        await callback.message.edit_text(
            f"✅ <b>Purchase Successful!</b>\n\n"
            f"📱 <b>Your Telegram ID:</b>\n"
            f"<code>{account.phone_number}</code>\n\n"
            f"💰 <b>Paid:</b> ₹{country.price}\n"
            f"💳 <b>Remaining Balance:</b> ₹{user.balance}\n\n"
            f"📋 <b>How to Login:</b>\n"
            f"1️⃣ Open Telegram app\n"
            f"2️⃣ Enter the phone number above\n"
            f"3️⃣ Telegram will ask for OTP\n"
            f"4️⃣ Click 'Get OTP Code' below\n"
            f"5️⃣ We'll send you the code instantly!\n\n"
            f"👇 <b>Ready to receive OTP?</b>",
            reply_markup=InlineKeyboardBuilder()
                .row(InlineKeyboardButton(
                    text="📲 Get OTP Code",
                    callback_data=f"get_otp_{purchase.id}"
                ))
                .row(InlineKeyboardButton(
                    text="🏠 Main Menu",
                    callback_data="btn_main_menu"
                ))
                .as_markup(),
            parse_mode="HTML"
        )


@dp.callback_query(F.data.startswith("get_otp_"))
async def process_get_otp(callback: types.CallbackQuery):
    """Start OTP monitoring for a purchase"""
    purchase_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        # Get purchase details
        purchase_stmt = select(Purchase).where(Purchase.id == purchase_id)
        purchase_res = await session.execute(purchase_stmt)
        purchase = purchase_res.scalar_one_or_none()
        
        if not purchase:
            await callback.answer("Purchase not found")
            return
        
        # Get account
        account_stmt = select(Account).where(Account.id == purchase.account_id)
        account_res = await session.execute(account_stmt)
        account = account_res.scalar_one_or_none()
        
        if not account or not account.session_data:
            await callback.message.edit_text(
                "❌ <b>Error!</b>\\n\\n"
                "This account doesn't have session data configured.\\n"
                "Please contact support.",
                reply_markup=InlineKeyboardBuilder()
                    .row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
                    .as_markup(),
                parse_mode="HTML"
            )
            return
        
        # Start monitoring
        try:
            logger.info(f"⚡ ATTEMPTING TO START MONITORING FOR {account.phone_number}")
            print(f"⚡ ATTEMPTING TO START MONITORING FOR {account.phone_number}")
            session_mgr = get_session_manager()
            await session_mgr.start_monitoring(
                phone_number=account.phone_number,
                session_string=account.session_data
            )
            
            # Delete the old message and send a new one to avoid "message not modified" error
            try:
                await callback.message.delete()
            except:
                pass  # If delete fails, just continue
            
            # Send new message with OTP waiting screen
            new_message = await bot.send_message(
                callback.message.chat.id,
                "🔄 <b>Starting OTP monitoring...</b>",
                parse_mode="HTML"
            )
            
            # Start the OTP waiting loop with new message
            await show_otp_waiting(new_message, account.phone_number, purchase_id)
            
        except Exception as e:
            logger.error(f"Error starting OTP monitoring: {e}")
            # Send error as new message instead of editing
            try:
                await bot.send_message(
                    callback.message.chat.id,
                    f"❌ <b>Error!</b>\n\n"
                    f"Failed to start OTP monitoring: {str(e)}\n\n"
                    "Please try again or contact support.",
                    reply_markup=InlineKeyboardBuilder()
                        .row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
                        .as_markup(),
                    parse_mode="HTML"
                )
            except Exception as edit_error:
                # If message edit fails (e.g., "message not modified"), just log it
                logger.error(f"Could not edit error message: {edit_error}")


async def show_otp_waiting(message: types.Message, phone_number: str, purchase_id: int, attempt: int = 0):
    """Show OTP waiting screen with manual check button"""
    session_mgr = get_session_manager()
    
    # Check if login successful
    login_status = await session_mgr.check_login_status(phone_number)
    if login_status == "LOGGED_IN":
        await message.edit_text(
            f"🎉 <b>LOGIN DONE SUCCESSFULLY!</b>\n\n"
            f"🙏 <b>Thanks for Purchasing!</b>\n\n"
            f"📱 <b>Phone:</b> <code>{phone_number}</code>\n"
            f"✅ <b>Status:</b> Login Verified\n\n"
            f"🎊 <b>Congratulations!</b>\n"
            f"Your Telegram account is now active and ready to use!\n\n"
            f"💡 <b>Important Notes:</b>\n"
            f"• Account is fully yours now\n"
            f"• Keep your password secure\n"
            f"• Don't share session data\n"
            f"• Follow Telegram's Terms of Service\n\n"
            f"✨ <b>Enjoy your new Telegram account!</b>",
            reply_markup=InlineKeyboardBuilder()
                .row(InlineKeyboardButton(text="🛠️ Manage Sessions", callback_data=f"manage_sess_{purchase_id}"))
                .row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
                .row(InlineKeyboardButton(text="🛍️ Buy More", callback_data="btn_accounts"))
                .as_markup(),
            parse_mode="HTML"
        )
        await session_mgr.stop_monitoring(phone_number)
        return
    
    # Check for OTP (Active Fetch)
    # Using check_latest_otp instead of get_otp to robustly find code even if listener fails
    otp_code = await session_mgr.check_latest_otp(phone_number)
    
    if otp_code:
        # Get 2FA password from database
        async with async_session() as db_session:
            purchase_stmt = select(Purchase).where(Purchase.id == purchase_id)
            purchase_res = await db_session.execute(purchase_stmt)
            purchase = purchase_res.scalar_one_or_none()
            
            twofa_password = None
            if purchase:
                account_stmt = select(Account).where(Account.id == purchase.account_id)
                account_res = await db_session.execute(account_stmt)
                account = account_res.scalar_one_or_none()
                if account:
                    twofa_password = account.twofa_password
        
        # Build message with OTP and optional 2FA password
        text = f"✅ <b>OTP Code Received!</b>\n\n"
        text += f"📱 <b>Phone:</b> <code>{phone_number}</code>\n"
        text += f"🔑 <b>OTP Code:</b> <code>{otp_code}</code>\n"
        
        if twofa_password:
            text += f"🔐 <b>2FA Password:</b> <code>{twofa_password}</code>\n"
        
        text += f"\n📋 <b>Next Steps:</b>\n"
        text += f"1️⃣ Copy the OTP code above\n"
        text += f"2️⃣ Enter it in Telegram app\n"
        
        if twofa_password:
            text += f"3️⃣ Enter the 2FA password when asked\n"
            text += f"4️⃣ Wait for login verification...\n\n"
        else:
            text += f"3️⃣ Wait for login verification...\n\n"
        
        text += f"🔄 <i>Auto-detecting login status...</i>\n"
        text += f"💡 <i>Click 'Resend Code' if needed</i>"
        
        # OTP received, show it with resend button
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardBuilder()
                .row(InlineKeyboardButton(
                    text="🔄 Resend Code",
                    callback_data=f"resend_otp_{purchase_id}"
                ))
                .row(InlineKeyboardButton(
                    text="⏹️ Stop Monitoring",
                    callback_data="btn_main_menu"
                ))
                .as_markup(),
            parse_mode="HTML"
        )
        # Continue monitoring for login
        await asyncio.sleep(5)
        await show_otp_waiting(message, phone_number, purchase_id, attempt + 1)
        
    # No OTP yet - show waiting message with manual check button
    # Add timestamp to show it's active
    current_time = datetime.now().strftime("%H:%M:%S")

    # No OTP yet - show waiting message with manual check button
    text = (
        f"⏳ <b>Waiting for your login...</b>\n\n"
        f"📱 <b>Phone:</b> <code>{phone_number}</code>\n\n"
        f"📋 <b>How to Login:</b>\n"
        f"1️⃣ Open <b>Telegram App</b> on your device\n"
        f"2️⃣ Tap '<b>Start Messaging</b>'\n"
        f"3️⃣ Enter this phone: <code>{phone_number}</code>\n"
        f"4️⃣ Request the verification code\n"
        f"5️⃣ Click 'Check for Code' button below!\n\n"
        f"💡 <i>Session monitoring is active</i>\n"
        f"🔄 <i>Auto-checking... ({attempt}/24)</i>\n"
        f"⏱️ <i>Refreshed: {current_time}</i>"
    )
    
    try:
        if attempt == 0:
             await message.edit_text(
                text,
                reply_markup=InlineKeyboardBuilder()
                    .row(InlineKeyboardButton(text="🔍 Check Code", callback_data=f"check_otp_{purchase_id}"))
                    .row(InlineKeyboardButton(text="⏹️ Stop Waiting", callback_data="btn_main_menu"))
                    .as_markup(),
                parse_mode="HTML"
            )
        else:
            await message.edit_text(
                text,
                reply_markup=InlineKeyboardBuilder()
                    .row(InlineKeyboardButton(text="🔍 Check Code", callback_data=f"check_otp_{purchase_id}"))
                    .row(InlineKeyboardButton(text="⏹️ Stop Waiting", callback_data="btn_main_menu"))
                    .as_markup(),
                parse_mode="HTML"
            )
    except Exception as e:
        # Ignore "message is not modified" errors
        if "message is not modified" not in str(e).lower():
             logger.error(f"Error editing message: {e}")
    
    # Continue monitoring for 2 minutes (24 * 5s = 120s)
    if attempt < 24:
        await asyncio.sleep(5)
        await show_otp_waiting(message, phone_number, purchase_id, attempt + 1)
    else:
         await message.edit_text(
            f"❌ <b>Timeout!</b>\n\n"
            f"We waited 2 minutes but didn't receive the code.\n"
            f"Please try again or contact support.",
            reply_markup=InlineKeyboardBuilder()
                 .row(InlineKeyboardButton(text="🔄 Try Again", callback_data=f"get_otp_{purchase_id}"))
                 .row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu"))
                 .as_markup(),
            parse_mode="HTML"
        )



@dp.callback_query(F.data.startswith("resend_otp_"))
async def process_resend_otp(callback: types.CallbackQuery):
    """Resend OTP request (clears cache and restarts monitoring)"""
    purchase_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        purchase_stmt = select(Purchase).where(Purchase.id == purchase_id)
        purchase_res = await session.execute(purchase_stmt)
        purchase = purchase_res.scalar_one_or_none()
        
        if not purchase:
            await callback.answer("Purchase not found")
            return
        
        account_stmt = select(Account).where(Account.id == purchase.account_id)
        account_res = await session.execute(account_stmt)
        account = account_res.scalar_one_or_none()
        
        if not account:
            await callback.answer("Account not found")
            return
        
        # Clear OTP cache and FORCE ACTIVE CHECK
        session_mgr = get_session_manager()
        session_mgr.clear_otp(account.phone_number)
        
        await callback.answer("Checking for new code...")
        
        # Active check to get the new code immediately
        await session_mgr.check_latest_otp(account.phone_number)
        
        await show_otp_waiting(callback.message, account.phone_number, purchase_id)
# Handler for manual OTP check
@dp.callback_query(F.data.startswith("check_otp_"))
async def handle_check_otp(callback: types.CallbackQuery):
    purchase_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        # Get purchase and account
        purchase_stmt = select(Purchase).where(Purchase.id == purchase_id)
        purchase_res = await session.execute(purchase_stmt)
        purchase = purchase_res.scalar_one_or_none()
        
        if not purchase:
            await callback.answer("Purchase not found")
            return
        
        account_stmt = select(Account).where(Account.id == purchase.account_id)
        account_res = await session.execute(account_stmt)
        account = account_res.scalar_one_or_none()
        
        if not account:
            await callback.answer("Account not found")
            return
        
        # Check if monitoring is active
        session_mgr = get_session_manager()
        login_status = await session_mgr.check_login_status(account.phone_number)
        
        if login_status == "NOT_MONITORING":
            await callback.answer("Reconnecting session...")
            try:
                # Restart monitoring
                await session_mgr.start_monitoring(
                    phone_number=account.phone_number,
                    session_string=account.session_data
                )
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Failed to restart monitoring: {e}")
                await callback.answer("Failed to reconnect session")
                return

        # FORCE ACTIVE CHECK: actively fetch history from 777000
        await callback.answer("Checking Telegram messages...")
        await session_mgr.check_latest_otp(account.phone_number)
        
        await show_otp_waiting(callback.message, account.phone_number, purchase_id)

# Handler for login status check
@dp.callback_query(F.data.startswith("check_login_"))
async def handle_check_login(callback: types.CallbackQuery):
    purchase_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        purchase_stmt = select(Purchase).where(Purchase.id == purchase_id)
        purchase_res = await session.execute(purchase_stmt)
        purchase = purchase_res.scalar_one_or_none()
        
        if not purchase:
            await callback.answer("Purchase not found")
            return
        
        account_stmt = select(Account).where(Account.id == purchase.account_id)
        account_res = await session.execute(account_stmt)
        account = account_res.scalar_one_or_none()
        
        if not account:
            await callback.answer("Account not found")
            return
        
        await callback.answer("Checking login status...")
        await show_otp_waiting(callback.message, account.phone_number, purchase_id)

# --- Device Management Handlers ---

@dp.callback_query(F.data.startswith("manage_sess_"))
async def process_manage_session(callback: types.CallbackQuery):
    """List active sessions for a purchase"""
    purchase_id = int(callback.data.split("_")[2])
    
    await callback.message.edit_text("🔄 <b>Connecting to Telegram...</b>\n\nPlease wait while we fetch active sessions...", parse_mode="HTML")
    
    async with async_session() as session:
        # Get Purchase -> Account -> Session String
        stmt = select(Purchase).where(Purchase.id == purchase_id)
        res = await session.execute(stmt)
        purchase = res.scalar_one_or_none()
        
        if not purchase:
            await callback.message.edit_text("❌ Purchase not found.", reply_markup=get_back_to_main())
            return
            
        stmt_acc = select(Account).where(Account.id == purchase.account_id)
        res_acc = await session.execute(stmt_acc)
        account = res_acc.scalar_one_or_none()
        
        if not account or not account.session_data:
            await callback.message.edit_text("❌ No session data found for this account.", reply_markup=get_back_to_main())
            return

        try:
            dm = DeviceManager()
            sessions = await dm.get_active_sessions(account.session_data)
            
            if not sessions:
                await callback.message.edit_text("❌ No active sessions found (weird).", reply_markup=get_back_to_main())
                return
                
            text = f"📱 <b>Active Sessions for {account.phone_number}</b>\n\n"
            text += "<i>Click '❌' to revoke a device instantly.</i>\n\n"
            
            builder = InlineKeyboardBuilder()
            
            for sess in sessions:
                # Mark current session (Bot)
                is_current = sess.get("is_current", False)
                
                device_name = f"{sess['device_model']} ({sess['platform']})"
                ip = sess['ip']
                
                status_icon = "🟢" if is_current else "⚪"
                
                # Build device button with X for removal
                if not is_current:
                    # Format: "Device Name     ❌"
                    btn_text = f"{sess['device_model'][:20]}... ❌"
                    builder.row(InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"kill_sess_{purchase_id}_{sess['hash']}"
                    ))
                    text += f"{status_icon} {device_name}\n"
                    text += f"   └ IP: {ip}\n\n"
                else:
                    # Current session - no delete button
                    text += f"{status_icon} {device_name} (Current)\n"
                    text += f"   └ IP: {ip}\n\n"
            
            text += f"💡 <i>Tap ❌ to remove a device</i>\n"
            
            builder.row(InlineKeyboardButton(text="🔄 Refresh", callback_data=f"manage_sess_{purchase_id}"))
            builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="btn_purchases"))
            
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Error managing sessions: {e}")
            await callback.message.edit_text(
                f"❌ <b>Error fetching sessions</b>\n\n{str(e)}",
                reply_markup=get_back_to_main(),
                parse_mode="HTML"
            )

@dp.callback_query(F.data.startswith("kill_sess_"))
async def process_kill_session(callback: types.CallbackQuery):
    """Terminate a session"""
    parts = callback.data.split("_")
    purchase_id = int(parts[2])
    session_hash = int(parts[3])
    
    await callback.answer("Revoking access...", show_alert=False)
    
    async with async_session() as session:
        # Get Account
        stmt = select(Purchase).where(Purchase.id == purchase_id)
        res = await session.execute(stmt)
        purchase = res.scalar_one_or_none()
        
        if not purchase: return
        
        stmt_acc = select(Account).where(Account.id == purchase.account_id)
        res_acc = await session.execute(stmt_acc)
        account = res_acc.scalar_one_or_none()
        
        if not account: return

        try:
            dm = DeviceManager()
            success = await dm.terminate_session(account.session_data, session_hash)
            
            if success:
                await callback.answer("✅ Device revoked successfully!", show_alert=True)
                # Refresh list
                await process_manage_session(callback)
            else:
                await callback.answer("❌ Failed to revoke.", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error killing session: {e}")
            await callback.answer(f"Error: {str(e)}", show_alert=True)
