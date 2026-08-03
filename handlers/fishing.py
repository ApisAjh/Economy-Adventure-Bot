"""
Handler /fish - memancing ikan dengan peluang berdasarkan kualitas pancing.
"""

import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import FISH_COOLDOWN_SECONDS
from database.database import get_session
from database.models import Inventory
from sqlalchemy import select
from utils.cooldown import check_cooldown, format_seconds, set_cooldown
from utils.economy import add_coin, add_xp, get_or_create_user
from utils.items import FISH_TYPES


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _has_pancing(session, user_id: int) -> bool:
    result = await session.execute(
        select(Inventory).where(Inventory.user_id == user_id, Inventory.item_name == "Pancing")
    )
    return result.scalar_one_or_none() is not None


async def _do_fish(tg_user) -> str:
    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        if not await _has_pancing(session, user.id):
            return "❌ Kamu butuh 🎣 Pancing untuk memancing. Beli dulu di /shop."

        allowed, remaining = await check_cooldown(session, user.id, "fish", FISH_COOLDOWN_SECONDS)
        if not allowed:
            return f"⏳ Pancing masih dipersiapkan. Coba lagi dalam {format_seconds(remaining)}."

        # Kualitas pancing (fixed, bisa dikembangkan lagi dengan level pancing) menambah peluang rare/legendary sedikit.
        fish = random.choices(FISH_TYPES, weights=[f["weight"] for f in FISH_TYPES], k=1)[0]
        coin_reward = random.randint(fish["min_coin"], fish["max_coin"])
        xp_reward = 20 if fish["rarity"] == "common" else 60 if fish["rarity"] == "rare" else 200

        await add_coin(user, coin_reward)
        await add_xp(user, xp_reward)
        await set_cooldown(session, user.id, "fish")

        return (
            f"{fish['emoji']} Kamu mendapatkan {fish['name']}!\n\n"
            f"💰 +{coin_reward} Coin\n"
            f"⭐ +{xp_reward} XP"
        )


async def fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return
    text = await _do_fish(tg_user)
    await update.message.reply_text(text, reply_markup=_back_button())


async def fish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()
    text = await _do_fish(tg_user)
    await query.edit_message_text(text, reply_markup=_back_button())
