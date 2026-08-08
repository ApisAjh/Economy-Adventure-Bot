"""
Koneksi database async (SQLAlchemy + asyncpg) ke PostgreSQL Supabase.
Hanya menggunakan DATABASE_URL, tidak menggunakan Supabase SDK sama sekali.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import ASYNC_DATABASE_URL
from utils.logger import logger

# NullPool cocok untuk lingkungan serverless (Vercel) karena setiap invocation
# bisa berjalan di proses terpisah, sehingga tidak perlu connection pool besar.
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    # PERF: pool_pre_ping sengaja TIDAK diaktifkan. pre_ping berguna untuk mendeteksi
    # koneksi basi yang diambil dari pool - tapi NullPool selalu membuka koneksi BARU
    # setiap kali (tidak pernah reuse), sehingga pre_ping di sini hanya menambah 1
    # round-trip "SELECT 1" ekstra ke database di SETIAP request tanpa manfaat nyata.
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Context manager async untuk mendapatkan session database dengan auto commit/rollback."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Database session error, rollback dilakukan.")
        raise
    finally:
        await session.close()
