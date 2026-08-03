"""
Fungsi inti ekonomi: manajemen user, coin, bank, xp/level, dan inventory.
Semua fungsi menerima AsyncSession aktif (tidak membuka session sendiri)
agar bisa digabung dalam satu transaksi oleh handler pemanggil.
"""

import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import STARTING_COIN, STARTING_LEVEL, XP_PER_LEVEL_BASE
from database.models import Inventory, User
from utils.items import SHOP_ITEMS
from utils.security import clamp_int


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None) -> tuple[User, bool]:
    """Mengambil user berdasarkan telegram_id, membuat akun baru jika belum ada."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is not None:
        # Update data ringan yang mungkin berubah (username/nama tampilan Telegram)
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if changed:
            await session.flush()
        return user, False

    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        coin=STARTING_COIN,
        bank=0,
        level=STARTING_LEVEL,
        xp=0,
        total_login=1,
        last_login=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()
    return user, True


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


def xp_required_for_level(level: int) -> int:
    """XP yang dibutuhkan untuk naik dari `level` ke `level + 1`."""
    return level * XP_PER_LEVEL_BASE


async def add_coin(user: User, amount: int) -> int:
    """Menambahkan coin ke dompet user. Amount boleh negatif untuk pengurangan terkontrol."""
    new_value = clamp_int(user.coin + amount, minimum=0)
    user.coin = new_value
    return new_value


async def remove_coin(user: User, amount: int) -> bool:
    """Mengurangi coin user. Return False jika saldo tidak cukup (coin tidak pernah negatif)."""
    if amount <= 0:
        return False
    if user.coin < amount:
        return False
    user.coin -= amount
    return True


async def add_xp(user: User, amount: int) -> list[int]:
    """
    Menambahkan XP ke user dan otomatis memproses level up (bisa naik >1 level sekaligus).
    Return daftar level baru yang dicapai (kosong jika tidak naik level).
    """
    if amount <= 0:
        return []

    user.xp += amount
    levels_gained: list[int] = []

    while user.xp >= xp_required_for_level(user.level):
        needed = xp_required_for_level(user.level)
        user.xp -= needed
        user.level += 1
        levels_gained.append(user.level)
        # Bonus coin setiap naik level
        await add_coin(user, user.level * 200)

    return levels_gained


async def add_item(session: AsyncSession, user_id: int, item_name: str, quantity: int) -> Inventory:
    """Menambahkan item ke inventory user. Jika item sudah ada, jumlahnya diakumulasikan (anti duplikasi entri)."""
    if quantity <= 0:
        raise ValueError("Quantity harus lebih dari 0")

    result = await session.execute(
        select(Inventory).where(Inventory.user_id == user_id, Inventory.item_name == item_name)
    )
    inv = result.scalar_one_or_none()

    if inv is None:
        inv = Inventory(user_id=user_id, item_name=item_name, quantity=quantity)
        session.add(inv)
    else:
        inv.quantity += quantity

    await session.flush()
    return inv


async def remove_item(session: AsyncSession, user_id: int, item_name: str, quantity: int) -> bool:
    """Mengurangi item dari inventory. Return False jika stok tidak cukup."""
    result = await session.execute(
        select(Inventory).where(Inventory.user_id == user_id, Inventory.item_name == item_name)
    )
    inv = result.scalar_one_or_none()

    if inv is None or inv.quantity < quantity:
        return False

    inv.quantity -= quantity
    if inv.quantity == 0:
        await session.delete(inv)

    await session.flush()
    return True


async def get_inventory(session: AsyncSession, user_id: int) -> list[Inventory]:
    result = await session.execute(select(Inventory).where(Inventory.user_id == user_id))
    return list(result.scalars().all())


async def calculate_net_worth(session: AsyncSession, user: User) -> int:
    """Kekayaan total = Coin + Bank + estimasi nilai item di inventory."""
    items = await get_inventory(session, user.id)
    item_value = 0
    for inv in items:
        price = SHOP_ITEMS.get(inv.item_name, {}).get("price", 0)
        item_value += price * inv.quantity
    return user.coin + user.bank + item_value


def weighted_choice(options: list[dict], weight_key: str = "weight") -> dict:
    """Memilih satu opsi secara random berdasarkan bobot (weight)."""
    weights = [opt[weight_key] for opt in options]
    return random.choices(options, weights=weights, k=1)[0]
