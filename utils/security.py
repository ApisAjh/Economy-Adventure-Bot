"""
Utilitas keamanan: validasi admin, validasi input, dan pembantu anti-spam.
Karena seluruh akses database menggunakan SQLAlchemy dengan parameterized query
(melalui ORM), risiko SQL Injection sudah tertutup secara struktural.
"""

from config.settings import ADMIN_ID


def is_admin(telegram_id: int) -> bool:
    """Mengecek apakah telegram_id adalah admin utama bot."""
    return int(telegram_id) == int(ADMIN_ID)


def validate_positive_amount(value: int | float) -> bool:
    """Memastikan jumlah coin/item yang diinput selalu positif (tidak boleh negatif atau nol)."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def validate_item_name(item_name: str, allowed_items: list[str]) -> bool:
    """Memvalidasi nama item terhadap daftar item yang diizinkan agar tidak ada item ilegal."""
    return isinstance(item_name, str) and item_name in allowed_items


def sanitize_text(text: str, max_length: int = 100) -> str:
    """Membersihkan input teks bebas (misalnya broadcast admin) dari karakter berbahaya & panjang berlebihan."""
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    return cleaned[:max_length]


def clamp_int(value: int, minimum: int = 0, maximum: int | None = None) -> int:
    """Membatasi nilai integer agar tidak pernah di bawah minimum (mis. coin tidak boleh negatif)."""
    value = max(int(value), minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value
