"""
Handler /profile - menampilkan profil lengkap pemain.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from utils.economy import get_inventory, get_or_create_user
from utils.economy import xp_required_for_level
from database.models import Pet
from sqlalchemy import select


async def _build_profile_text(session, user, display_name: str) -> str:
    items = await get_inventory(session, user.id)
    total_items = sum(inv.quantity for inv in items)

    pet_result = await session.execute(select(Pet).where(Pet.user_id == user.id))
    pets = pet_result.scalars().all()
    pet_text = ", ".join(f"{p.pet_type} (Lv.{p.pet_level})" for p in pets) if pets else "Tidak ada"

    xp_needed = xp_required_for_level(user.level)

    return (
        "👤 Profil\n\n"
        f"Nama: {display_name}\n"
        f"Level: {user.level}\n"
        f"XP: {user.xp}/{xp_needed}\n\n"
        f"💰 Coin: {user.coin}\n"
        f"🏦 Bank: {user.bank}\n\n"
        f"💼 Pekerjaan: {user.job or 'Belum bekerja'}\n\n"
        f"🏠 Rumah: {user.house or 'Belum punya'}\n"
        f"🚗 Kendaraan: {user.vehicle or 'Belum punya'}\n\n"
        f"🎒 Inventory: {total_items} item\n"
        f"🐶 Pet: {pet_text}"
    )


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_profile_text(session, user, user.full_name or tg_user.first_name)

    await update.message.reply_text(text, reply_markup=_back_button())


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_profile_text(session, user, user.full_name or tg_user.first_name)

    await query.edit_message_text(text, reply_markup=_back_button())
