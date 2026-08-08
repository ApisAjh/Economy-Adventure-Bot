"""
Handler /admin - panel admin lengkap.
Hanya bisa diakses oleh Telegram User ID yang sama dengan ADMIN_ID di .env
"""

import io
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.settings import BOT_VERSION
from database.database import get_session
from database.models import (
    Achievement,
    BankTransaction,
    Cooldown,
    Event,
    Farming,
    Inventory,
    Market,
    Pet,
    User,
)
from utils.economy import add_coin, get_user_by_telegram_id, remove_coin
from utils.logger import logger
from utils.security import is_admin, sanitize_text, validate_positive_amount

ACCESS_DENIED_TEXT = "❌ Kamu tidak memiliki izin untuk menggunakan perintah ini."

# Nama-nama action yang membutuhkan input teks lanjutan dari admin.
AWAITING_KEY = "admin_awaiting"


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📊 Statistik Bot", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Total User", callback_data="admin_totaluser")],
        [InlineKeyboardButton("💰 Tambah Coin", callback_data="admin_addcoin"),
         InlineKeyboardButton("💸 Kurangi Coin", callback_data="admin_subcoin")],
        [InlineKeyboardButton("🎁 Berikan Item", callback_data="admin_giveitem")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
         InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎉 Aktifkan Event", callback_data="admin_activateevent")],
        [InlineKeyboardButton("⏸ Maintenance ON", callback_data="admin_maintenance_on"),
         InlineKeyboardButton("▶ Maintenance OFF", callback_data="admin_maintenance_off")],
        [InlineKeyboardButton("🔄 Reset Cooldown", callback_data="admin_resetcooldown")],
        [InlineKeyboardButton("🗑 Hapus Akun", callback_data="admin_deleteaccount")],
        [InlineKeyboardButton("📦 Backup Database", callback_data="admin_backup")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    if not is_admin(tg_user.id):
        await update.message.reply_text(ACCESS_DENIED_TEXT)
        return

    await update.message.reply_text("🛠 Panel Admin\n\nPilih menu:", reply_markup=admin_menu_keyboard())


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return

    if not is_admin(tg_user.id):
        await query.answer(ACCESS_DENIED_TEXT, show_alert=True)
        return

    await query.answer()
    action = query.data

    if action == "admin_stats":
        text = await _build_stats_text(context)
        await query.edit_message_text(text, reply_markup=admin_menu_keyboard())
        return

    if action == "admin_totaluser":
        async with get_session() as session:
            total = (await session.execute(select(func.count(User.id)))).scalar_one()
        await query.edit_message_text(f"👥 Total User: {total}", reply_markup=admin_menu_keyboard())
        return

    if action == "admin_maintenance_on":
        context.bot_data["maintenance_mode"] = True
        await query.edit_message_text("⏸ Maintenance mode diaktifkan.", reply_markup=admin_menu_keyboard())
        return

    if action == "admin_maintenance_off":
        context.bot_data["maintenance_mode"] = False
        await query.edit_message_text("▶ Maintenance mode dinonaktifkan.", reply_markup=admin_menu_keyboard())
        return

    if action == "admin_backup":
        await _send_backup(update, context)
        return

    # Action yang butuh input lanjutan dari admin (dikirim sebagai pesan teks biasa)
    prompts = {
        "admin_addcoin": "Kirim: <telegram_id> <jumlah>\nContoh: 123456789 5000",
        "admin_subcoin": "Kirim: <telegram_id> <jumlah>\nContoh: 123456789 5000",
        "admin_giveitem": "Kirim: <telegram_id> <nama_item> <jumlah>\nContoh: 123456789 Diamond 5",
        "admin_ban": "Kirim: <telegram_id>\nContoh: 123456789",
        "admin_unban": "Kirim: <telegram_id>\nContoh: 123456789",
        "admin_broadcast": "Kirim pesan yang ingin di-broadcast ke semua user.",
        "admin_activateevent": "Kirim: <nama_event> <multiplier> <durasi_menit>\nContoh: Weekend Double Coin 2 1440",
        "admin_resetcooldown": "Kirim: <telegram_id>\n(kosongkan cooldown akan direset untuk semua command)",
        "admin_deleteaccount": "Kirim: <telegram_id>\n⚠️ Akun akan dihapus permanen!",
    }

    if action in prompts:
        context.user_data[AWAITING_KEY] = action
        await query.edit_message_text(
            f"✍️ {prompts[action]}\n\nKetik /cancel untuk membatalkan.",
        )
        return


async def admin_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None or not is_admin(tg_user.id):
        return
    context.user_data.pop(AWAITING_KEY, None)
    await update.message.reply_text("❎ Dibatalkan.", reply_markup=admin_menu_keyboard())


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani input teks lanjutan setelah admin menekan salah satu tombol admin."""
    tg_user = update.effective_user
    message = update.message
    if tg_user is None or message is None or not is_admin(tg_user.id):
        return

    awaiting = context.user_data.get(AWAITING_KEY)
    if not awaiting:
        return  # bukan alur admin, biarkan handler lain yang menangani

    text = message.text or ""
    parts = text.strip().split(maxsplit=2)
    context.user_data.pop(AWAITING_KEY, None)

    try:
        if awaiting == "admin_addcoin":
            await _admin_add_coin(message, parts, positive=True)
        elif awaiting == "admin_subcoin":
            await _admin_add_coin(message, parts, positive=False)
        elif awaiting == "admin_giveitem":
            await _admin_give_item(message, parts)
        elif awaiting == "admin_ban":
            await _admin_set_ban(message, parts, banned=True)
        elif awaiting == "admin_unban":
            await _admin_set_ban(message, parts, banned=False)
        elif awaiting == "admin_broadcast":
            await _admin_broadcast(message, context, text)
        elif awaiting == "admin_activateevent":
            await _admin_activate_event(message, parts, text)
        elif awaiting == "admin_resetcooldown":
            await _admin_reset_cooldown(message, parts)
        elif awaiting == "admin_deleteaccount":
            await _admin_delete_account(message, parts)
    except Exception:
        logger.exception("Error saat memproses aksi admin: %s", awaiting)
        await message.reply_text("❌ Terjadi kesalahan saat memproses aksi ini.")

    await message.reply_text("Kembali ke menu admin:", reply_markup=admin_menu_keyboard())


async def _admin_add_coin(message, parts: list[str], positive: bool) -> None:
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.reply_text("Format salah. Contoh: 123456789 5000")
        return

    telegram_id = int(parts[0])
    amount = int(parts[1])

    if not validate_positive_amount(amount):
        await message.reply_text("Jumlah harus lebih dari 0.")
        return

    async with get_session() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.reply_text("❌ User tidak ditemukan.")
            return

        if positive:
            await add_coin(user, amount)
            await message.reply_text(f"✅ +{amount} coin diberikan ke {telegram_id}. Saldo sekarang: {user.coin}")
        else:
            success = await remove_coin(user, amount)
            if not success:
                user.coin = 0
                await message.reply_text(f"⚠️ Saldo user kurang dari {amount}, coin diset ke 0.")
            else:
                await message.reply_text(f"✅ -{amount} coin dari {telegram_id}. Saldo sekarang: {user.coin}")


async def _admin_give_item(message, parts: list[str]) -> None:
    if len(parts) < 3:
        await message.reply_text("Format salah. Contoh: 123456789 Diamond 5")
        return

    telegram_id_str, item_name, qty_str = parts[0], parts[1], parts[2]
    if not telegram_id_str.isdigit():
        await message.reply_text("Telegram ID harus berupa angka.")
        return

    # qty bisa mengandung sisa teks jika nama item mengandung spasi; ambil token terakhir sebagai qty
    tokens = qty_str.strip().split()
    qty_token = tokens[-1] if tokens else qty_str
    if not qty_token.isdigit():
        await message.reply_text("Jumlah item harus berupa angka.")
        return

    quantity = int(qty_token)
    item_name = sanitize_text(item_name, 100)

    from utils.economy import add_item

    async with get_session() as session:
        user = await get_user_by_telegram_id(session, int(telegram_id_str))
        if user is None:
            await message.reply_text("❌ User tidak ditemukan.")
            return
        await add_item(session, user.id, item_name, quantity)

    await message.reply_text(f"✅ {quantity}x {item_name} diberikan ke {telegram_id_str}.")


async def _admin_set_ban(message, parts: list[str], banned: bool) -> None:
    if not parts or not parts[0].isdigit():
        await message.reply_text("Format salah. Contoh: 123456789")
        return

    telegram_id = int(parts[0])
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.reply_text("❌ User tidak ditemukan.")
            return
        user.is_banned = banned

    status = "diban 🚫" if banned else "di-unban ✅"
    await message.reply_text(f"User {telegram_id} berhasil {status}.")


async def _admin_broadcast(message, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    broadcast_text = sanitize_text(text, max_length=4000)

    async with get_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_banned.is_(False)))
        telegram_ids = [row[0] for row in result.all()]

    sent, failed = 0, 0
    for tid in telegram_ids:
        try:
            await context.bot.send_message(chat_id=tid, text=f"📢 Pengumuman\n\n{broadcast_text}")
            sent += 1
        except Exception:
            failed += 1

    await message.reply_text(f"📢 Broadcast selesai.\n✅ Terkirim: {sent}\n❌ Gagal: {failed}")


async def _admin_activate_event(message, parts: list[str], raw_text: str) -> None:
    tokens = raw_text.strip().split()
    if len(tokens) < 3:
        await message.reply_text("Format salah. Contoh: Weekend Double Coin 2 1440")
        return

    try:
        duration_minutes = int(tokens[-1])
        multiplier = float(tokens[-2])
        event_name = sanitize_text(" ".join(tokens[:-2]), 100)
    except ValueError:
        await message.reply_text("Format salah. Pastikan multiplier dan durasi berupa angka.")
        return

    from datetime import timedelta

    now = datetime.now(timezone.utc)
    async with get_session() as session:
        event = Event(
            event_name=event_name,
            description=f"Event aktif selama {duration_minutes} menit.",
            multiplier=multiplier,
            active=True,
            start_time=now,
            end_time=now + timedelta(minutes=duration_minutes),
        )
        session.add(event)

    await message.reply_text(f"🎉 Event '{event_name}' diaktifkan dengan multiplier x{multiplier} selama {duration_minutes} menit.")


async def _admin_reset_cooldown(message, parts: list[str]) -> None:
    if not parts or not parts[0].isdigit():
        await message.reply_text("Format salah. Contoh: 123456789")
        return

    telegram_id = int(parts[0])
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.reply_text("❌ User tidak ditemukan.")
            return

        result = await session.execute(select(Cooldown).where(Cooldown.user_id == user.id))
        cooldowns = result.scalars().all()
        for c in cooldowns:
            await session.delete(c)

    await message.reply_text(f"🔄 Semua cooldown user {telegram_id} berhasil direset.")


async def _admin_delete_account(message, parts: list[str]) -> None:
    if not parts or not parts[0].isdigit():
        await message.reply_text("Format salah. Contoh: 123456789")
        return

    telegram_id = int(parts[0])
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.reply_text("❌ User tidak ditemukan.")
            return
        await session.delete(user)

    await message.reply_text(f"🗑 Akun {telegram_id} berhasil dihapus permanen.")


async def _build_stats_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    # PERF: versi lama melakukan 8 query COUNT/SUM terpisah secara berurutan (8 round-trip
    # ke database). Digabung menjadi 1 SELECT dengan scalar subquery per metrik -> 1 round-trip.
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    stats_query = select(
        select(func.count(User.id)).scalar_subquery().label("total_user"),
        select(func.count(User.id)).where(User.last_login >= today_start).scalar_subquery().label("active_today"),
        select(func.coalesce(func.sum(User.coin + User.bank), 0)).scalar_subquery().label("total_coin"),
        select(func.count(BankTransaction.id)).scalar_subquery().label("total_transactions"),
        select(func.coalesce(func.sum(Inventory.quantity), 0)).scalar_subquery().label("total_item"),
        select(func.count(Pet.id)).scalar_subquery().label("total_pet"),
        select(func.count(User.id)).where(User.house.is_not(None)).scalar_subquery().label("total_house"),
        select(func.count(User.id)).where(User.vehicle.is_not(None)).scalar_subquery().label("total_vehicle"),
    )

    async with get_session() as session:
        row = (await session.execute(stats_query)).one()

    (
        total_user,
        active_today,
        total_coin,
        total_transactions,
        total_item,
        total_pet,
        total_house,
        total_vehicle,
    ) = row

    maintenance = context.bot_data.get("maintenance_mode", False)

    return (
        "📊 Statistik Bot\n\n"
        f"👥 Total User: {total_user}\n"
        f"🟢 User Aktif Hari Ini: {active_today}\n"
        f"💰 Total Coin Beredar: {total_coin}\n"
        f"🔁 Total Transaksi: {total_transactions}\n"
        f"🎒 Total Item: {total_item}\n"
        f"🐶 Total Pet: {total_pet}\n"
        f"🏠 Total Rumah: {total_house}\n"
        f"🚗 Total Kendaraan: {total_vehicle}\n\n"
        f"🤖 Bot Version: {BOT_VERSION}\n"
        f"🛠 Maintenance Mode: {'AKTIF' if maintenance else 'NONAKTIF'}"
    )


async def _send_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return

    def _row_to_dict(row) -> dict:
        data = {}
        for column in row.__table__.columns:
            value = getattr(row, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            data[column.name] = value
        return data

    async with get_session() as session:
        tables = {
            "users": (await session.execute(select(User))).scalars().all(),
            "inventory": (await session.execute(select(Inventory))).scalars().all(),
            "pets": (await session.execute(select(Pet))).scalars().all(),
            "bank_transactions": (await session.execute(select(BankTransaction))).scalars().all(),
            "market": (await session.execute(select(Market))).scalars().all(),
            "farming": (await session.execute(select(Farming))).scalars().all(),
            "achievements": (await session.execute(select(Achievement))).scalars().all(),
            "events": (await session.execute(select(Event))).scalars().all(),
        }

        backup_data = {name: [_row_to_dict(row) for row in rows] for name, rows in tables.items()}

    json_bytes = json.dumps(backup_data, indent=2, ensure_ascii=False).encode("utf-8")
    file_buffer = io.BytesIO(json_bytes)
    file_buffer.name = f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=file_buffer,
        filename=file_buffer.name,
        caption="📦 Backup database berhasil dibuat.",
    )
    await query.edit_message_text("📦 Backup berhasil dikirim sebagai file.", reply_markup=admin_menu_keyboard())
