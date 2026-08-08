"""
Utilitas untuk sistem pasangan (couple): query relasi aktif, cek status single/menikah,
dan helper love level. Semua fungsi menerima AsyncSession aktif dari handler pemanggil
(pola yang sama seperti utils/economy.py) agar tetap satu transaksi per command.
"""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Couple, User

PROPOSAL_EXPIRY_SECONDS = 5 * 60  # 5 menit


async def get_active_couple(session: AsyncSession, user_id: int) -> Couple | None:
    """Mengambil baris couples aktif milik user_id, baik dia berperan sebagai user_id maupun partner_id."""
    result = await session.execute(
        select(Couple).where(
            Couple.status == "active",
            or_(Couple.user_id == user_id, Couple.partner_id == user_id),
        )
    )
    return result.scalar_one_or_none()


async def get_active_couple_locked(session: AsyncSession, user_id: int) -> Couple | None:
    """Sama seperti get_active_couple, tetapi mengunci baris (SELECT ... FOR UPDATE)
    agar aman dari race condition saat proses accept/divorce berjalan bersamaan."""
    result = await session.execute(
        select(Couple)
        .where(
            Couple.status == "active",
            or_(Couple.user_id == user_id, Couple.partner_id == user_id),
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


def get_partner_id(couple: Couple, user_id: int) -> int:
    """Mengembalikan user_id pasangan dari sebuah baris Couple, relatif terhadap user_id yang diberikan."""
    return couple.partner_id if couple.user_id == user_id else couple.user_id


async def get_partner_display(session: AsyncSession, couple: Couple, user_id: int) -> str:
    """Mengembalikan nama tampilan pasangan (untuk ditampilkan di profile/love)."""
    partner_id = get_partner_id(couple, user_id)
    partner = await session.get(User, partner_id)
    if partner is None:
        return "Tidak diketahui"
    return partner.full_name or partner.username or f"Player{partner.id}"


def relationship_days(couple: Couple) -> int:
    now = datetime.now(timezone.utc)
    created = couple.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max((now - created).days, 0)
