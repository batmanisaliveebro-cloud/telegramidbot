"""
Bot Settings Handlers - Admin can change channel link and owner username
"""

# Add to bot.py after other handlers

@dp.callback_query(F.data == "btn_bot_settings")
async def show_bot_settings(callback: types.CallbackQuery):
    """Show bot settings menu (admin only)"""
    user_id = callback.from_user.id
    
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == user_id))
        user = user.scalar_one_or_none()
        
        if not user or not user.is_admin:
            await callback.answer("❌ Admin access required", show_alert=True)
            return
        
        # Fetch current settings
        settings_result = await session.execute(
            select(Settings).where(Settings.key.in_(['bot_channel_link', 'bot_owner_username']))
        )
        settings_dict = {s.key: s.value for s in settings_result.scalars().all()}
        
        channel_link = settings_dict.get('bot_channel_link', 'Not set')
        owner_username = settings_dict.get('bot_owner_username', 'Not set')
        
        text = (
            "⚙️ <b>Bot Settings</b>\n\n"
            f"📢 <b>Channel Link:</b> {channel_link}\n"
            f"👨‍💼 <b>Owner Username:</b> {owner_username}\n\n"
            "Choose what to update:"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📢 Change Channel", callback_data="set_channel_link")
        )
        builder.row(
            InlineKeyboardButton(text="👨‍💼 Change Owner", callback_data="set_owner_username")
        )
        builder.row(
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="btn_main_menu")
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "set_channel_link")
async def request_channel_link(callback: types.CallbackQuery, state: FSMContext):
    """Request new channel link from admin"""
    await callback.message.edit_text(
        "📢 <b>Update Channel Link</b>\n\n"
        "Send me the new Telegram channel link.\n"
        "Example: https://t.me/yourchannel\n\n"
        "Or send /cancel to abort.",
        parse_mode="HTML"
    )
    await state.set_state(BotSettingsStates.waiting_for_channel_link)


@dp.message(BotSettingsStates.waiting_for_channel_link)
async def save_channel_link(message: types.Message, state: FSMContext):
    """Save new channel link to database"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", reply_markup=get_main_menu(is_admin=True))
        return
    
    channel_link = message.text.strip()
    
    # Basic validation
    if not channel_link.startswith("https://t.me/"):
        await message.answer(
            "❌ Invalid link! Must start with https://t.me/\n\n"
            "Try again or send /cancel"
        )
        return
    
    # Save to database
    async with async_session() as session:
        setting = await session.execute(
            select(Settings).where(Settings.key == 'bot_channel_link')
        )
        setting = setting.scalar_one_or_none()
        
        if setting:
            setting.value = channel_link
        else:
            setting = Settings(key='bot_channel_link', value=channel_link)
            session.add(setting)
        
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"✅ <b>Channel link updated!</b>\n\n"
        f"New link: {channel_link}",
        reply_markup=get_main_menu(is_admin=True),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "set_owner_username")
async def request_owner_username(callback: types.CallbackQuery, state: FSMContext):
    """Request new owner username from admin"""
    await callback.message.edit_text(
        "👨‍💼 <b>Update Owner Username</b>\n\n"
        "Send me the new owner username.\n"
        "Example: @yourusername\n\n"
        "Or send /cancel to abort.",
        parse_mode="HTML"
    )
    await state.set_state(BotSettingsStates.waiting_for_owner_username)


@dp.message(BotSettingsStates.waiting_for_owner_username)
async def save_owner_username(message: types.Message, state: FSMContext):
    """Save new owner username to database"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", reply_markup=get_main_menu(is_admin=True))
        return
    
    owner_username = message.text.strip()
    
    # Save to database (with or without @)
    if not owner_username.startswith('@'):
        owner_username = f'@{owner_username}'
    
    async with async_session() as session:
        setting = await session.execute(
            select(Settings).where(Settings.key == 'bot_owner_username')
        )
        setting = setting.scalar_one_or_none()
        
        if setting:
            setting.value = owner_username
        else:
            setting = Settings(key='bot_owner_username', value=owner_username)
            session.add(setting)
        
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"✅ <b>Owner username updated!</b>\n\n"
        f"New username: {owner_username}",
        reply_markup=get_main_menu(is_admin=True),
        parse_mode="HTML"
    )
