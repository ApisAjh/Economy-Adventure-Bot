"""
Handler /start - membuat akun otomatis dan menampilkan menu utama.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import STARTING_COIN, STARTING_LEVEL
from database.database import get_session
from utils.economy import get_or_create_user
from utils.logger import logger


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("👤 Profile", callback_data="menu_profile"),
         InlineKeyboardButton("💼 Work", callback_data="menu_work")],
        [InlineKeyboardButton("🎁 Daily", callback_data="menu_daily"),
         InlineKeyboardButton("🏦 Bank", callback_data="menu_bank")],
        [InlineKeyboardButton("🛒 Shop", callback_data="menu_shop"),
         InlineKeyboardButton("🎒 Inventory", callback_data="menu_inventory")],
        [InlineKeyboardButton("🌾 Farm", callback_data="menu_farm"),
         InlineKeyboardButton("🎣 Fish", callback_data="menu_fish")],
        [InlineKeyboardButton("⛏ Mine", callback_data="menu_mine"),
         InlineKeyboardButton("🐶 Pet", callback_data="menu_pet")],
        [InlineKeyboardButton("⚔️ Duel", callback_data="menu_duel"),
         InlineKeyboardButton("🏆 Ranking", callback_data="menu_ranking")],
        [InlineKeyboardButton("📜 Achievement", callback_data="menu_achievement"),
         InlineKeyboardButton("🎉 Event", callback_data="menu_event")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, created = await get_or_create_user(
            session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )

        if not created:
            user.total_login += 1

        coin = user.coin
        level = user.level
        name = user.full_name or tg_user.first_name or "Player"

    if created:
        logger.info("User baru terdaftar: %s (%s)", tg_user.id, tg_user.username)
        text = (
            f"👤 {name}\n\n"
            f"💰 Coin : {STARTING_COIN}\n"
            f"⭐ Level : {STARTING_LEVEL}\n\n"
            "Selamat datang di Economy Adventure! 🎉\n"
            "Akun kamu berhasil dibuat.\n\n"
            "Pilih aktivitas di bawah ini:"
        )
    else:
        text = (
            f"👤 {name}\n\n"
            f"💰 Coin : {coin}\n"
            f"⭐ Level : {level}\n\n"
            "Selamat datang kembali di Economy Adventure!\n\n"
            "Pilih aktivitas di bawah ini:"
        )

    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani tombol 'kembali ke menu' dari berbagai fitur."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    await query.edit_message_text("🏠 Menu Utama\n\nPilih aktivitas:", reply_markup=main_menu_keyboard())
