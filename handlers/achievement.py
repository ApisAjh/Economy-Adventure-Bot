"""
Handler /achievement - menampilkan progress achievement pemain dan otomatis
memberi reward saat achievement baru saja tercapai.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import Achievement, User
from utils.economy import add_coin, get_or_create_user
from utils.items import ACHIEVEMENTS

ACHIEVEMENT_REWARD_COIN = 5000


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


def _is_target_reached(user: User, check_field: str, target) -> bool:
    value = getattr(user, check_field, None)
    if isinstance(target, bool):
        return bool(value)
    if value is None:
        return False
    return value >= target


async def _sync_achievements(session, user: User) -> list[str]:
    """Mengecek dan mencatat achievement baru yang tercapai. Return daftar nama achievement baru."""
    result = await session.execute(select(Achievement).where(Achievement.user_id == user.id))
    existing = {a.achievement: a for a in result.scalars().all()}

    newly_completed = []

    for name, data in ACHIEVEMENTS.items():
        reached = _is_target_reached(user, data["check"], data["target"])
        record = existing.get(name)

        if record is None:
            record = Achievement(user_id=user.id, achievement=name, completed=False)
            session.add(record)
            await session.flush()

        if reached and not record.completed:
            record.completed = True
            record.completed_at = datetime.now(timezone.utc)
            await add_coin(user, ACHIEVEMENT_REWARD_COIN)
            newly_completed.append(name)

    return newly_completed


async def _build_achievement_text(session, user: User) -> str:
    newly_completed = await _sync_achievements(session, user)

    result = await session.execute(select(Achievement).where(Achievement.user_id == user.id))
    records = {a.achievement: a for a in result.scalars().all()}

    lines = ["📜 Achievement\n"]
    for name, data in ACHIEVEMENTS.items():
        record = records.get(name)
        status = "✅" if record and record.completed else "⬜"
        lines.append(f"{status} {data['emoji']} {name} — {data['description']}")

    if newly_completed:
        lines.append("\n🎉 Achievement baru tercapai!")
        for name in newly_completed:
            lines.append(f"🏆 {name} (+{ACHIEVEMENT_REWARD_COIN} Coin)")

    return "\n".join(lines)


async def achievement_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_achievement_text(session, user)

    await update.message.reply_text(text, reply_markup=_back_button())


async def achievement_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_achievement_text(session, user)

    await query.edit_message_text(text, reply_markup=_back_button())
