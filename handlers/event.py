"""
Handler /event - menampilkan event yang sedang aktif.
Event dibuat/diaktifkan oleh admin melalui /admin.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import Event


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def get_active_multiplier(session) -> float:
    """Mengembalikan multiplier tertinggi dari event yang sedang aktif (dipakai fitur lain jika perlu)."""
    now = datetime.now(timezone.utc)
    result = await session.execute(select(Event).where(Event.active.is_(True)))
    events = result.scalars().all()

    multiplier = 1.0
    for e in events:
        start_ok = e.start_time is None or e.start_time.replace(tzinfo=timezone.utc) <= now
        end_ok = e.end_time is None or e.end_time.replace(tzinfo=timezone.utc) >= now
        if start_ok and end_ok:
            multiplier = max(multiplier, e.multiplier)

    return multiplier


async def _build_event_text(session) -> str:
    result = await session.execute(select(Event).where(Event.active.is_(True)))
    events = result.scalars().all()

    if not events:
        return "🎉 Tidak ada event yang sedang aktif saat ini."

    lines = ["🎉 Event Aktif\n"]
    for e in events:
        lines.append(f"🔥 {e.event_name} — Multiplier x{e.multiplier}")
        if e.description:
            lines.append(f"   {e.description}")

    return "\n".join(lines)


async def event_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    async with get_session() as session:
        text = await _build_event_text(session)
    await update.message.reply_text(text, reply_markup=_back_button())


async def event_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    async with get_session() as session:
        text = await _build_event_text(session)
    await query.edit_message_text(text, reply_markup=_back_button())
