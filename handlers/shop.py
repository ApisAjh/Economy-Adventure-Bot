"""
Handler /shop - menampilkan toko dan memproses pembelian item.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from utils.economy import add_item, get_or_create_user, remove_coin
from utils.items import SHOP_ITEMS


def shop_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for name, data in SHOP_ITEMS.items():
        row.append(InlineKeyboardButton(f"{data['emoji']} {name} - {data['price']}", callback_data=f"buy_{name}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def _shop_text() -> str:
    lines = ["🛒 Shop\n"]
    for name, data in SHOP_ITEMS.items():
        lines.append(f"{data['emoji']} {name} — 💰 {data['price']}")
    lines.append("\nTekan tombol item untuk membeli 1 pcs.")
    return "\n".join(lines)


async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(_shop_text(), reply_markup=shop_keyboard())


async def shop_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    await query.edit_message_text(_shop_text(), reply_markup=shop_keyboard())


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None or query.data is None:
        return

    item_name = query.data.removeprefix("buy_")
    item = SHOP_ITEMS.get(item_name)

    if item is None:
        await query.answer("Item tidak ditemukan.", show_alert=True)
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        success = await remove_coin(user, item["price"])
        if not success:
            await query.answer("❌ Coin kamu tidak cukup!", show_alert=True)
            return

        if item["category"] == "house":
            user.house = item_name
        elif item["category"] == "vehicle":
            user.vehicle = item_name
        elif item["category"] == "pet":
            from database.models import Pet
            from utils.items import PET_TYPES
            import random as _random
            pet_def = _random.choice(PET_TYPES)
            session.add(Pet(user_id=user.id, pet_type=pet_def["name"], pet_level=1, bonus=pet_def["base_bonus"]))
        else:
            await add_item(session, user.id, item_name, 1)

        remaining_coin = user.coin

    await query.answer(f"✅ Berhasil membeli {item_name}!", show_alert=True)
    await query.edit_message_text(
        f"✅ Kamu membeli {item['emoji']} {item_name}!\n💰 Sisa Coin: {remaining_coin}",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🛒 Kembali ke Shop", callback_data="menu_shop")],
                [InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")],
            ]
        ),
    )
