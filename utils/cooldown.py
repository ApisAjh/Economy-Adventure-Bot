"""
Utilitas pengelolaan cooldown per user per command, disimpan di tabel `cooldown`.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Cooldown


async def check_cooldown(session: AsyncSession, user_id: int, command: str, seconds: int) -> tuple[bool, int]:
    """
    Mengecek apakah user boleh menjalankan command.
    Return (allowed, remaining_seconds).
    """
    result = await session.execute(
        select(Cooldown).where(Cooldown.user_id == user_id, Cooldown.command == command)
    )
    row = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if row is None:
        return True, 0

    last_used = row.last_used
    if last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=timezone.utc)

    elapsed = (now - last_used).total_seconds()
    remaining = seconds - elapsed

    if remaining > 0:
        return False, int(remaining)

    return True, 0


async def set_cooldown(session: AsyncSession, user_id: int, command: str) -> None:
    """Menyimpan/mereset waktu cooldown terakhir untuk user + command tertentu.

    PERF/SAFETY: memakai INSERT ... ON CONFLICT (upsert) dalam SATU query, memanfaatkan
    unique constraint (user_id, command) di tabel cooldown. Ini menggantikan pola lama
    "SELECT lalu INSERT-atau-UPDATE" (2 round-trip + rawan race condition menghasilkan
    baris duplikat jika dua request untuk command yang sama diproses hampir bersamaan).
    """
    now = datetime.now(timezone.utc)

    stmt = pg_insert(Cooldown).values(user_id=user_id, command=command, last_used=now)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Cooldown.user_id, Cooldown.command],
        set_={"last_used": now},
    )
    await session.execute(stmt)
    await session.flush()


def format_seconds(seconds: int) -> str:
    """Format detik menjadi teks yang mudah dibaca, contoh: '5 menit 30 detik'."""
    seconds = max(int(seconds), 0)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    parts = []
    if hours:
        parts.append(f"{hours} jam")
    if minutes:
        parts.append(f"{minutes} menit")
    if sec or not parts:
        parts.append(f"{sec} detik")
    return " ".join(parts)
