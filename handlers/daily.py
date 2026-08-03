"""
Handler /daily - reward harian dengan cooldown 24 jam.
"""

import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import DAILY_COOLDOWN_SECONDS
from database.database import get_session
from utils.cooldown import check_cooldown, format_seconds, set_cooldown
from utils.economy import add_coin, add_item, get_or_create_user


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _do_daily(tg_user) -> str:
    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        allowed, remaining = await check_cooldown(session, user.id, "daily", DAILY_COOLDOWN_SECONDS)
        if not allowed:
            return f"⏳ Daily reward sudah diambil. Coba lagi dalam {format_seconds(remaining)}."

        coin_reward = random.randint(1000, 3000)
        diamond_reward = random.randint(1, 3)
        got_lucky_box = random.random() < 0.2

        await add_coin(user, coin_reward)
        await add_item(session, user.id, "Diamond", diamond_reward)

        text = (
            "🎁 Daily Reward\n\n"
            f"💰 +{coin_reward} Coin\n"
            f"💎 +{diamond_reward} Diamond"
        )

        if got_lucky_box:
            await add_item(session, user.id, "Lucky Box", 1)
            text += "\n🎁 +1 Lucky Box (Bonus!)"

        await set_cooldown(session, user.id, "daily")
        return text


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return
    text = await _do_daily(tg_user)
    await update.message.reply_text(text, reply_markup=_back_button())


async def daily_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()
    text = await _do_daily(tg_user)
    await query.edit_message_text(text, reply_markup=_back_button())
