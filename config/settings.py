"""
Konfigurasi global bot, dimuat dari environment variables (.env).
Tidak ada token / ID yang ditulis langsung di kode.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, required: bool = True, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(
            f"Environment variable '{name}' wajib diisi. Cek file .env atau Environment Variables di Vercel."
        )
    return value


BOT_TOKEN: str = _get_env("BOT_TOKEN")
WEBHOOK_URL: str = _get_env("WEBHOOK_URL")
ADMIN_ID: int = int(_get_env("ADMIN_ID"))
DATABASE_URL: str = _get_env("DATABASE_URL")
BOT_VERSION: str = _get_env("BOT_VERSION", required=False, default="1.0.0")

# SQLAlchemy async membutuhkan driver asyncpg secara eksplisit.
# Jika user mengisi DATABASE_URL dengan format standar postgresql://,
# otomatis dikonversi menjadi postgresql+asyncpg://
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# ---- Konstanta ekonomi ----
STARTING_COIN = 5000
STARTING_LEVEL = 1

WORK_COOLDOWN_SECONDS = 10 * 60          # 10 menit
DAILY_COOLDOWN_SECONDS = 24 * 60 * 60    # 24 jam
FARM_BASE_SECONDS = 5 * 60               # 5 menit dasar untuk panen
FISH_COOLDOWN_SECONDS = 60               # 1 menit
MINE_COOLDOWN_SECONDS = 90               # 1.5 menit
DUEL_COOLDOWN_SECONDS = 5 * 60           # 5 menit

XP_PER_LEVEL_BASE = 100  # xp dibutuhkan level n = n * XP_PER_LEVEL_BASE
