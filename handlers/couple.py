"""
Handler sistem pasangan (couple).

Command:
/propose @username   -> melamar user lain (atau reply pesan user tsb dengan /propose)
/couple               -> lihat status pasangan
/divorce              -> mengakhiri hubungan (butuh konfirmasi tombol)
/love                 -> lihat love level & lama hubungan

Semua operasi tulis (accept/divorce) menggunakan row lock (SELECT ... FOR UPDATE)
di dalam satu transaksi (satu `get_session()`), sehingga aman dari race condition
tanpa perlu query tambahan di luar transaksi.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import Couple, CoupleProposal, User
from utils.couple import (
    PROPOSAL_EXPIRY_SECONDS,
    get_active_couple,
    get_active_couple_locked,
    get_partner_display,
    get_partner_id,
    relationship_days,
)
from utils.economy import get_or_create_user
from utils.logger import logger

PROPOSAL_SPAM_COOLDOWN_SECONDS = 60  # jeda antar lamaran baru dari sender yang sama


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


def _proposal_keyboard(proposal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💚 TERIMA", callback_data=f"coupleaccept_{proposal_id}"),
                InlineKeyboardButton("❌ TOLAK", callback_data=f"coupledecline_{proposal_id}"),
            ]
        ]
    )


def _divorce_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💔 Ya, Cerai", callback_data="divorce_confirm"),
                InlineKeyboardButton("Batal", callback_data="divorce_cancel"),
            ]
        ]
    )


async def _resolve_target(session, message, tg_user, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    """Menentukan target lamaran: prioritas reply-to-message, fallback ke argumen @username
    (username hanya bisa ditemukan jika user tersebut sudah pernah /start bot ini)."""

    if message.reply_to_message is not None and message.reply_to_message.from_user is not None:
        target_tg = message.reply_to_message.from_user
        if target_tg.is_bot:
            await message.reply_text("❌ Kamu tidak bisa melamar bot.")
            return None
        if target_tg.id == tg_user.id:
            await message.reply_text("❌ Kamu tidak bisa melamar diri sendiri.")
            return None
        target, _ = await get_or_create_user(session, target_tg.id, target_tg.username, target_tg.full_name)
        return target

    args = context.args or []
    if not args:
        await message.reply_text(
            "💍 Gunakan: /propose @username\nAtau reply pesan orangnya dengan /propose."
        )
        return None

    username = args[0].lstrip("@").strip().lower()
    if not username:
        await message.reply_text("Format salah. Contoh: /propose @username")
        return None

    result = await session.execute(select(User).where(User.username.ilike(username)))
    target = result.scalar_one_or_none()

    if target is None:
        await message.reply_text(
            "❌ User tidak ditemukan. Pastikan dia sudah pernah /start bot ini, "
            "atau balas (reply) pesannya langsung dengan /propose."
        )
        return None

    if target.telegram_id == tg_user.id:
        await message.reply_text("❌ Kamu tidak bisa melamar diri sendiri.")
        return None

    return target


async def propose_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    message = update.message
    if tg_user is None or message is None:
        return

    async with get_session() as session:
        sender, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        target = await _resolve_target(session, message, tg_user, context)
        if target is None:
            return

        # Kunci baris couples kedua user agar status single/married tidak berubah
        # di tengah proses pengecekan (mencegah double marriage).
        sender_couple = await get_active_couple_locked(session, sender.id)
        if sender_couple is not None:
            await message.reply_text("❌ Kamu sudah punya pasangan. /divorce dulu jika ingin melamar orang lain.")
            return

        target_couple = await get_active_couple_locked(session, target.id)
        if target_couple is not None:
            await message.reply_text("❌ Orang itu sudah memiliki pasangan.")
            return

        now = datetime.now(timezone.utc)

        # Anti-spam: batalkan/expire proposal pending lama dari sender ini sebelum membuat yang baru,
        # dan cegah spam lamaran beruntun ke target yang sama.
        result = await session.execute(
            select(CoupleProposal)
            .where(
                CoupleProposal.sender_id == sender.id,
                CoupleProposal.receiver_id == target.id,
                CoupleProposal.status == "pending",
            )
            .with_for_update()
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing_expires = existing.expires_at
            if existing_expires.tzinfo is None:
                existing_expires = existing_expires.replace(tzinfo=timezone.utc)
            if existing_expires > now:
                await message.reply_text("⏳ Kamu masih punya lamaran pending ke orang ini. Tunggu balasannya dulu.")
                return
            existing.status = "expired"

        proposal = CoupleProposal(
            sender_id=sender.id,
            receiver_id=target.id,
            status="pending",
            expires_at=now + timedelta(seconds=PROPOSAL_EXPIRY_SECONDS),
        )
        session.add(proposal)
        await session.flush()

        sender_name = sender.full_name or tg_user.first_name
        target_telegram_id = target.telegram_id
        proposal_id = proposal.id

    text = f"💍 Lamaran!\n\n\"{sender_name}\" ingin menjadi pasanganmu.\n\nApakah kamu menerima?"

    try:
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=text,
            reply_markup=_proposal_keyboard(proposal_id),
        )
    except Exception:
        logger.exception("Gagal mengirim pesan lamaran.")
        await message.reply_text("❌ Terjadi kesalahan saat mengirim lamaran.")
        return

    await message.reply_text(f"✅ Lamaran terkirim! Menunggu balasan dalam {PROPOSAL_EXPIRY_SECONDS // 60} menit.")


async def _handle_proposal_response(update: Update, context: ContextTypes.DEFAULT_TYPE, accept: bool) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None or query.data is None:
        return

    try:
        proposal_id = int(query.data.split("_", maxsplit=1)[1])
    except (IndexError, ValueError):
        await query.answer()
        return

    async with get_session() as session:
        responder, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        result = await session.execute(
            select(CoupleProposal).where(CoupleProposal.id == proposal_id).with_for_update()
        )
        proposal = result.scalar_one_or_none()

        if proposal is None:
            await query.answer("❌ Lamaran tidak ditemukan.", show_alert=True)
            return

        # Validasi identitas HANYA dari data proposal di database, tidak pernah dari
        # asumsi apapun di callback data selain proposal_id itu sendiri.
        if proposal.receiver_id != responder.id:
            await query.answer("❌ Lamaran ini bukan untukmu.", show_alert=True)
            return

        if proposal.status != "pending":
            await query.answer("❌ Lamaran ini sudah tidak berlaku.", show_alert=True)
            return

        now = datetime.now(timezone.utc)
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            proposal.status = "expired"
            await query.answer("⏳ Lamaran sudah kedaluwarsa.", show_alert=True)
            await query.edit_message_text("💔 Lamaran sudah kedaluwarsa.")
            return

        await query.answer()

        if not accept:
            proposal.status = "rejected"
            await query.edit_message_text("❌ Lamaran ditolak.")
            return

        sender = await session.get(User, proposal.sender_id)
        if sender is None:
            proposal.status = "expired"
            await query.edit_message_text("❌ Terjadi kesalahan: pengirim lamaran tidak ditemukan.")
            return

        # Kunci ulang status single kedua user di dalam transaksi accept (bukan hanya saat /propose)
        # untuk menutup celah race condition antara waktu propose dan waktu accept ditekan.
        sender_couple = await get_active_couple_locked(session, sender.id)
        if sender_couple is not None:
            proposal.status = "expired"
            await query.edit_message_text("❌ Pengirim lamaran sudah memiliki pasangan lain.")
            return

        receiver_couple = await get_active_couple_locked(session, responder.id)
        if receiver_couple is not None:
            proposal.status = "expired"
            await query.edit_message_text("❌ Kamu sudah memiliki pasangan.")
            return

        couple = Couple(user_id=sender.id, partner_id=responder.id, love_level=0, status="active")
        session.add(couple)
        proposal.status = "accepted"

        sender_name = sender.full_name or sender.username or f"Player{sender.id}"
        responder_name = responder.full_name or responder.username or f"Player{responder.id}"

    await query.edit_message_text(f"💞 Selamat! {sender_name} & {responder_name} sekarang resmi menjadi pasangan!")


async def couple_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_proposal_response(update, context, accept=True)


async def couple_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_proposal_response(update, context, accept=False)


async def _build_couple_text(session, user: User) -> str:
    couple = await get_active_couple(session, user.id)
    if couple is None:
        return "💞 Kamu masih single.\n\nGunakan /propose @username untuk melamar seseorang."

    partner_name = await get_partner_display(session, couple, user.id)
    days = relationship_days(couple)

    return (
        "💞 Status Pasangan\n\n"
        f"❤️ Pasangan: {partner_name}\n"
        f"💕 Love Level: {couple.love_level}\n"
        f"📅 Bersama selama: {days} hari\n\n"
        "Gunakan /love untuk detail, atau /divorce untuk mengakhiri hubungan."
    )


async def couple_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_couple_text(session, user)

    await update.message.reply_text(text, reply_markup=_back_button())


async def couple_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = await _build_couple_text(session, user)

    await query.edit_message_text(text, reply_markup=_back_button())


async def love_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        couple = await get_active_couple(session, user.id)

        if couple is None:
            await update.message.reply_text(
                "💔 Kamu belum punya pasangan.\nGunakan /propose @username untuk melamar seseorang.",
                reply_markup=_back_button(),
            )
            return

        partner_name = await get_partner_display(session, couple, user.id)
        days = relationship_days(couple)
        display_name = user.full_name or tg_user.first_name

    text = (
        "❤️ LOVE STATUS\n\n"
        f"👤 {display_name}\n"
        f"💞 Pasangan: {partner_name}\n\n"
        f"❤️ Love Level: {couple.love_level}\n"
        f"💕 Relationship: {days} hari"
    )
    await update.message.reply_text(text, reply_markup=_back_button())


async def divorce_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        couple = await get_active_couple(session, user.id)

        if couple is None:
            await update.message.reply_text("❌ Kamu belum memiliki pasangan.")
            return

        partner_name = await get_partner_display(session, couple, user.id)

    await update.message.reply_text(
        f"💔 Yakin ingin bercerai dengan {partner_name}?",
        reply_markup=_divorce_confirm_keyboard(),
    )


async def divorce_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        # Lock baris couple agar tidak ada dua proses divorce/accept yang menabrak baris yang sama.
        couple = await get_active_couple_locked(session, user.id)

        if couple is None:
            await query.answer("❌ Kamu tidak punya pasangan (mungkin sudah bercerai).", show_alert=True)
            await query.edit_message_text("❌ Kamu tidak memiliki pasangan.")
            return

        await query.answer()

        couple.status = "ended"
        couple.ended_at = datetime.now(timezone.utc)

    # Divorce TIDAK menyentuh balance/inventory apapun sesuai spesifikasi.
    await query.edit_message_text("💔 Kamu telah resmi bercerai.")


async def divorce_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    await query.edit_message_text("❎ Perceraian dibatalkan.")
