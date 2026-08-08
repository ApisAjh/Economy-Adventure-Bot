"""
Handler /market - marketplace antar pemain (jual/beli item).

Format:
/market                         -> lihat listing yang terbuka
/market sell <item> <qty> <price> -> pasang barang untuk dijual
/market buy <id>                -> membeli listing berdasarkan id
/market cancel <id>              -> membatalkan listing milik sendiri
"""

from sqlalchemy import select

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import Market
from utils.economy import add_coin, add_item, get_or_create_user, remove_coin, remove_item
from utils.security import sanitize_text, validate_positive_amount


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


async def _list_market(session) -> str:
    result = await session.execute(select(Market).where(Market.status == "open").order_by(Market.created_at.desc()).limit(15))
    listings = result.scalars().all()

    if not listings:
        return "🏪 Market kosong. Jadilah yang pertama menjual barang!\n\nGunakan: /market sell <item> <qty> <harga>"

    lines = ["🏪 Market — Barang Dijual\n"]
    for m in listings:
        lines.append(f"#{m.id} — {m.item_name} x{m.quantity} — 💰 {m.price}")
    lines.append("\nGunakan /market buy <id> untuk membeli.")
    return "\n".join(lines)


async def market_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    args = context.args or []

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        if not args:
            text = await _list_market(session)
            await update.message.reply_text(text, reply_markup=_back_button())
            return

        action = args[0].lower()

        if action == "sell" and len(args) >= 4:
            item_name = sanitize_text(args[1], max_length=100)
            try:
                quantity = int(args[2])
                price = int(args[3])
            except ValueError:
                await update.message.reply_text("Format salah. Contoh: /market sell Emas 5 3000")
                return

            if not validate_positive_amount(quantity) or not validate_positive_amount(price):
                await update.message.reply_text("Jumlah dan harga harus lebih dari 0.")
                return

            success = await remove_item(session, user.id, item_name, quantity)
            if not success:
                await update.message.reply_text("❌ Item tidak ditemukan atau jumlah tidak cukup di inventory kamu.")
                return

            listing = Market(seller_id=user.id, item_name=item_name, quantity=quantity, price=price, status="open")
            session.add(listing)
            await session.flush()

            await update.message.reply_text(
                f"✅ Listing dibuat!\n#{listing.id} — {item_name} x{quantity} — 💰 {price}",
                reply_markup=_back_button(),
            )
            return

        if action == "buy" and len(args) >= 2:
            try:
                listing_id = int(args[1])
            except ValueError:
                await update.message.reply_text("Format salah. Contoh: /market buy 3")
                return

            # PERF/SAFETY: FOR UPDATE mengunci baris listing ini sampai transaksi selesai,
            # sehingga dua pembeli yang menekan /market buy <id> bersamaan tidak bisa
            # keduanya lolos pengecekan status=='open' sebelum salah satunya commit
            # (mencegah exploit "double sell" satu listing).
            result = await session.execute(
                select(Market).where(Market.id == listing_id, Market.status == "open").with_for_update()
            )
            listing = result.scalar_one_or_none()

            if listing is None:
                await update.message.reply_text("❌ Listing tidak ditemukan atau sudah terjual.")
                return

            if listing.seller_id == user.id:
                await update.message.reply_text("❌ Kamu tidak bisa membeli barangmu sendiri.")
                return

            success = await remove_coin(user, listing.price)
            if not success:
                await update.message.reply_text("❌ Coin kamu tidak cukup.")
                return

            from database.models import User
            seller = await session.get(User, listing.seller_id)
            if seller:
                await add_coin(seller, listing.price)

            await add_item(session, user.id, listing.item_name, listing.quantity)
            listing.status = "sold"

            await update.message.reply_text(
                f"✅ Kamu membeli {listing.item_name} x{listing.quantity} seharga 💰 {listing.price}",
                reply_markup=_back_button(),
            )
            return

        if action == "cancel" and len(args) >= 2:
            try:
                listing_id = int(args[1])
            except ValueError:
                await update.message.reply_text("Format salah. Contoh: /market cancel 3")
                return

            result = await session.execute(
                select(Market).where(Market.id == listing_id, Market.status == "open").with_for_update()
            )
            listing = result.scalar_one_or_none()

            if listing is None or listing.seller_id != user.id:
                await update.message.reply_text("❌ Listing tidak ditemukan atau bukan milikmu.")
                return

            listing.status = "cancelled"
            await add_item(session, user.id, listing.item_name, listing.quantity)

            await update.message.reply_text(f"✅ Listing #{listing.id} dibatalkan dan barang dikembalikan.", reply_markup=_back_button())
            return

        await update.message.reply_text(
            "Perintah market tidak dikenali.\n\n"
            "Gunakan:\n"
            "/market\n"
            "/market sell <item> <qty> <harga>\n"
            "/market buy <id>\n"
            "/market cancel <id>"
        )


async def market_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    async with get_session() as session:
        text = await _list_market(session)

    await query.edit_message_text(text, reply_markup=_back_button())
