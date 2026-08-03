"""
Script migrasi database sederhana.
Membuat semua tabel yang didefinisikan di database/models.py jika belum ada.

Cara pakai (lokal):
    python -m database.migrations
"""

import asyncio

from database.database import engine
from database.models import Base
from utils.logger import logger


async def init_db() -> None:
    """Membuat semua tabel di PostgreSQL Supabase jika belum tersedia."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Migrasi database selesai. Semua tabel sudah siap.")


async def drop_all() -> None:
    """WARNING: menghapus semua tabel. Gunakan hanya untuk keperluan development/reset."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("Semua tabel telah dihapus dari database.")


if __name__ == "__main__":
    asyncio.run(init_db())
