"""
Handler /ranking - Top 10 pemain berdasarkan total kekayaan (Coin + Bank + Nilai Item).
"""

from collections import defaultdict

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import ADMIN_ID
from database.database import get_session
from database.models import Inventory, User
from utils.items import SHOP_ITEMS


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _build_ranking_text(session) -> str:
    # PERF: versi lama memanggil calculate_net_worth() per user di dalam loop, yang
    # masing-masing melakukan 1 query inventory sendiri -> total 1 + N query (N+1).
    # Di sini kita ambil semua user + SEMUA baris inventory HANYA dalam 2 query total,
    # lalu agregasi nilai item dilakukan di memory (harga item statis dari SHOP_ITEMS,
    # bukan dari DB, jadi tidak bisa dihitung lewat SQL JOIN langsung).
    users_result = await session.execute(
        select(User.id, User.telegram_id, User.username, User.full_name, User.coin, User.bank).where(
            User.is_banned.is_(False), User.telegram_id != ADMIN_ID
        )
    )
    users = users_result.all()

    if not users:
        return "🏆 Belum ada data pemain untuk ranking."

    user_ids = [u.id for u in users]

    inv_result = await session.execute(
        select(Inventory.user_id, Inventory.item_name, Inventory.quantity).where(Inventory.user_id.in_(user_ids))
    )
    item_value_by_user: dict[int, int] = defaultdict(int)
    for user_id, item_name, quantity in inv_result.all():
        price = SHOP_ITEMS.get(item_name, {}).get("price", 0)
        item_value_by_user[user_id] += price * quantity

    scored = [
        (u, u.coin + u.bank + item_value_by_user.get(u.id, 0))
        for u in users
    ]

    scored.sort(key=lambda pair: pair[1], reverse=True)
    top10 = scored[:10]

    if not top10:
        return "🏆 Belum ada data pemain untuk ranking."

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Ranking — Top 10 Pemain Terkaya\n"]
    for i, (u, net_worth) in enumerate(top10):
        icon = medals[i] if i < 3 else f"{i + 1}."
        name = u.full_name or u.username or f"Player{u.telegram_id}"
        lines.append(f"{icon} {name} — 💰 {net_worth}")

    return "\n".join(lines)


async def ranking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    async with get_session() as session:
        text = await _build_ranking_text(session)
    await update.message.reply_text(text, reply_markup=_back_button())


async def ranking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    async with get_session() as session:
        text = await _build_ranking_text(session)
    await query.edit_message_text(text, reply_markup=_back_button())
