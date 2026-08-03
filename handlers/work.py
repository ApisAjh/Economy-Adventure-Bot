"""
Handler /work - bekerja untuk mendapatkan coin dan xp, dengan cooldown 10 menit.
"""

import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import WORK_COOLDOWN_SECONDS
from database.database import get_session
from utils.cooldown import check_cooldown, format_seconds, set_cooldown
from utils.economy import add_coin, add_xp, get_or_create_user
from utils.items import JOBS


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _do_work(tg_user) -> str:
    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        allowed, remaining = await check_cooldown(session, user.id, "work", WORK_COOLDOWN_SECONDS)
        if not allowed:
            return f"⏳ Kamu masih lelah! Coba lagi dalam {format_seconds(remaining)}."

        job = random.choice(JOBS)
        coin_reward = random.randint(job["min_coin"], job["max_coin"])

        await add_coin(user, coin_reward)
        levels_gained = await add_xp(user, job["xp"])
        user.job = job["name"]
        user.total_work += 1

        await set_cooldown(session, user.id, "work")

        text = (
            f"{job['emoji']} Kamu bekerja sebagai {job['name']}\n\n"
            f"💰 +{coin_reward} Coin\n"
            f"⭐ +{job['xp']} XP"
        )
        if levels_gained:
            text += f"\n\n⭐ LEVEL UP! Sekarang level {user.level} 🎉"

        return text


async def work_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return
    text = await _do_work(tg_user)
    await update.message.reply_text(text, reply_markup=_back_button())


async def work_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()
    text = await _do_work(tg_user)
    await query.edit_message_text(text, reply_markup=_back_button())
