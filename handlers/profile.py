"""
Handler /profile - menampilkan profil lengkap pemain.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from utils.economy import get_or_create_user
from utils.economy import xp_required_for_level
from utils.couple import get_active_couple, get_partner_display
from database.models import Inventory, Pet
from sqlalchemy import func, select


async def _build_profile_text(session, user, display_name: str) -> str:
    # Sebelumnya profile melakukan 2 query terpisah (get_inventory lalu Pet select).
    # Untuk profile kita hanya butuh TOTAL quantity item (bukan detail per-item), jadi
    # cukup 1 query SUM() di level database (tidak menarik semua baris inventory ke Python).
    total_items = (
        await session.execute(select(func.coalesce(func.sum(Inventory.quantity), 0)).where(Inventory.user_id == user.id))
    ).scalar_one()

    pet_result = await session.execute(select(Pet.pet_type, Pet.pet_level).where(Pet.user_id == user.id))
    pets = pet_result.all()
    pet_text = ", ".join(f"{name} (Lv.{level})" for name, level in pets) if pets else "Tidak ada"

    xp_needed = xp_required_for_level(user.level)

    # Info pasangan bersifat opsional (tidak wajib untuk profile), tapi query-nya sudah
    # memakai partial unique index jadi murah (index lookup, bukan scan).
    couple = await get_active_couple(session, user.id)
    partner_line = ""
    if couple is not None:
        partner_name = await get_partner_display(session, couple, user.id)
        partner_line = f"\n❤️ Pasangan: {partner_name}"

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
        f"{partner_line}"
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
