"""
Handler /pet - menampilkan dan melatih pet milik pemain.
Pet memberikan bonus coin & keberuntungan (bonus disimpan di kolom `bonus`).

Format:
/pet          -> lihat semua pet
/pet train <id> -> melatih pet untuk naik level (butuh coin)
"""

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import Pet
from utils.economy import get_or_create_user, remove_coin
from utils.items import PET_TYPES

TRAIN_COST_PER_LEVEL = 500


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _list_pets_text(session, user_id: int) -> str:
    result = await session.execute(select(Pet).where(Pet.user_id == user_id))
    pets = result.scalars().all()

    if not pets:
        return "🐶 Kamu belum punya pet.\nBeli di /shop untuk mendapatkan pet random!"

    lines = ["🐶 Pet Kamu\n"]
    for p in pets:
        emoji = next((pt["emoji"] for pt in PET_TYPES if pt["name"] == p.pet_type), "🐾")
        lines.append(f"#{p.id} {emoji} {p.pet_type} — Level {p.pet_level} — Bonus {p.bonus * 100:.1f}%")

    lines.append(f"\nLatih pet: /pet train <id> (biaya {TRAIN_COST_PER_LEVEL} x level saat ini)")
    return "\n".join(lines)


async def pet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    args = context.args or []

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        if not args:
            text = await _list_pets_text(session, user.id)
            await update.message.reply_text(text, reply_markup=_back_button())
            return

        if args[0].lower() == "train" and len(args) >= 2:
            try:
                pet_id = int(args[1])
            except ValueError:
                await update.message.reply_text("Format salah. Contoh: /pet train 1")
                return

            result = await session.execute(select(Pet).where(Pet.id == pet_id, Pet.user_id == user.id))
            pet = result.scalar_one_or_none()

            if pet is None:
                await update.message.reply_text("❌ Pet tidak ditemukan.")
                return

            cost = TRAIN_COST_PER_LEVEL * pet.pet_level
            success = await remove_coin(user, cost)
            if not success:
                await update.message.reply_text(f"❌ Butuh 💰 {cost} coin untuk melatih pet ini.")
                return

            pet.pet_level += 1
            pet.bonus = round(pet.bonus + 0.01, 4)

            await update.message.reply_text(
                f"🐾 {pet.pet_type} naik ke Level {pet.pet_level}!\nBonus sekarang: {pet.bonus * 100:.1f}%",
                reply_markup=_back_button(),
            )
            return

        await update.message.reply_text("Perintah tidak dikenali. Gunakan /pet atau /pet train <id>.")


async def pet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _list_pets_text(session, user.id)

    await query.edit_message_text(text, reply_markup=_back_button())
