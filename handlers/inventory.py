"""
Handler /inventory - menampilkan semua barang milik pemain.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from utils.economy import get_inventory, get_or_create_user
from utils.items import SHOP_ITEMS


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _build_inventory_text(session, user) -> str:
    items = await get_inventory(session, user.id)

    if not items:
        return "🎒 Inventory kamu masih kosong.\nBeli item di /shop untuk memulai!"

    lines = ["🎒 Inventory\n"]
    for inv in items:
        emoji = SHOP_ITEMS.get(inv.item_name, {}).get("emoji", "📦")
        lines.append(f"{emoji} {inv.item_name} x{inv.quantity}")

    if user.house:
        lines.append(f"\n🏠 Rumah: {user.house}")
    if user.vehicle:
        lines.append(f"🚗 Kendaraan: {user.vehicle}")

    return "\n".join(lines)


async def inventory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_inventory_text(session, user)

    await update.message.reply_text(text, reply_markup=_back_button())


async def inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_inventory_text(session, user)

    await query.edit_message_text(text, reply_markup=_back_button())
