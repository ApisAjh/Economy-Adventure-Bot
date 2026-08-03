"""
Handler /mine - menambang untuk mendapatkan batu, besi, emas, atau diamond.
"""

import random

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import MINE_COOLDOWN_SECONDS
from database.database import get_session
from database.models import Inventory
from utils.cooldown import check_cooldown, format_seconds, set_cooldown
from utils.economy import add_coin, add_xp, get_or_create_user
from utils.items import ORE_TYPES


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _has_pickaxe(session, user_id: int) -> bool:
    result = await session.execute(
        select(Inventory).where(Inventory.user_id == user_id, Inventory.item_name == "Pickaxe")
    )
    return result.scalar_one_or_none() is not None


async def _do_mine(tg_user) -> str:
    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        if not await _has_pickaxe(session, user.id):
            return "❌ Kamu butuh ⛏ Pickaxe untuk menambang. Beli dulu di /shop."

        allowed, remaining = await check_cooldown(session, user.id, "mine", MINE_COOLDOWN_SECONDS)
        if not allowed:
            return f"⏳ Kamu masih lelah menambang. Coba lagi dalam {format_seconds(remaining)}."

        ore = random.choices(ORE_TYPES, weights=[o["weight"] for o in ORE_TYPES], k=1)[0]
        coin_reward = random.randint(ore["min_coin"], ore["max_coin"])
        xp_reward = 15 if ore["name"] == "Batu" else 40 if ore["name"] == "Besi" else 100 if ore["name"] == "Emas" else 250

        await add_coin(user, coin_reward)
        await add_xp(user, xp_reward)
        await set_cooldown(session, user.id, "mine")

        return (
            f"{ore['emoji']} Kamu menambang {ore['name']}!\n\n"
            f"💰 +{coin_reward} Coin\n"
            f"⭐ +{xp_reward} XP"
        )


async def mine_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return
    text = await _do_mine(tg_user)
    await update.message.reply_text(text, reply_markup=_back_button())


async def mine_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()
    text = await _do_mine(tg_user)
    await query.edit_message_text(text, reply_markup=_back_button())
