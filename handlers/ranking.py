"""
Handler /ranking - Top 10 pemain berdasarkan total kekayaan (Coin + Bank + Nilai Item).
"""

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import User
from utils.economy import calculate_net_worth


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _build_ranking_text(session) -> str:
    result = await session.execute(select(User).where(User.is_banned.is_(False)))
    users = result.scalars().all()

    scored = []
    for u in users:
        net_worth = await calculate_net_worth(session, u)
        scored.append((u, net_worth))

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
