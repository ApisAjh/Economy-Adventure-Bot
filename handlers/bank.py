"""
Handler bank: /deposit, /withdraw, /bank
"""

from sqlalchemy import select, desc
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import BankTransaction
from utils.economy import get_or_create_user
from utils.security import validate_positive_amount


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


def _parse_amount(args: list[str]) -> int | None:
    if not args:
        return None
    try:
        amount = int(args[0])
    except ValueError:
        return None
    if not validate_positive_amount(amount):
        return None
    return amount


async def deposit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    amount = _parse_amount(context.args)
    if amount is None:
        await update.message.reply_text("Gunakan format: /deposit <jumlah>\nContoh: /deposit 1000")
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        if user.coin < amount:
            await update.message.reply_text("❌ Coin kamu tidak cukup untuk deposit sebesar itu.")
            return

        user.coin -= amount
        user.bank += amount
        session.add(BankTransaction(user_id=user.id, transaction_type="deposit", amount=amount))

        coin, bank_balance = user.coin, user.bank

    await update.message.reply_text(
        f"🏦 Deposit berhasil!\n\n💰 Coin: {coin}\n🏦 Bank: {bank_balance}",
        reply_markup=_back_button(),
    )


async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    amount = _parse_amount(context.args)
    if amount is None:
        await update.message.reply_text("Gunakan format: /withdraw <jumlah>\nContoh: /withdraw 1000")
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        if user.bank < amount:
            await update.message.reply_text("❌ Saldo bank kamu tidak cukup.")
            return

        user.bank -= amount
        user.coin += amount
        session.add(BankTransaction(user_id=user.id, transaction_type="withdraw", amount=amount))

        coin, bank_balance = user.coin, user.bank

    await update.message.reply_text(
        f"🏦 Withdraw berhasil!\n\n💰 Coin: {coin}\n🏦 Bank: {bank_balance}",
        reply_markup=_back_button(),
    )


async def bank_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        result = await session.execute(
            select(BankTransaction)
            .where(BankTransaction.user_id == user.id)
            .order_by(desc(BankTransaction.created_at))
            .limit(5)
        )
        transactions = result.scalars().all()

        text = f"🏦 Bank\n\n💰 Coin: {user.coin}\n🏦 Saldo Bank: {user.bank}\n\n"
        if transactions:
            text += "📜 Riwayat transaksi terakhir:\n"
            for trx in transactions:
                icon = "⬇️" if trx.transaction_type == "deposit" else "⬆️"
                text += f"{icon} {trx.transaction_type.capitalize()}: {trx.amount} coin\n"
        else:
            text += "Belum ada riwayat transaksi."

    await update.message.reply_text(text, reply_markup=_back_button())


async def bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        text = (
            f"🏦 Bank\n\n💰 Coin: {user.coin}\n🏦 Saldo Bank: {user.bank}\n\n"
            "Gunakan perintah:\n"
            "/deposit <jumlah>\n/withdraw <jumlah>\n/bank untuk riwayat"
        )

    await query.edit_message_text(text, reply_markup=_back_button())
