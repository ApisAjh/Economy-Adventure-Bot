"""
Entry point webhook Telegram untuk Vercel Serverless.

Bot berjalan SEPENUHNYA menggunakan webhook (tidak ada polling sama sekali).
FastAPI menerima update dari Telegram di endpoint POST /api/webhook,
lalu diteruskan ke python-telegram-bot Application untuk diproses.
"""

import sys
from pathlib import Path

# Memastikan root project bisa diimport saat dijalankan sebagai Vercel Function.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import ADMIN_ID, BOT_TOKEN, BOT_VERSION
from handlers import (
    achievement,
    admin,
    bank,
    daily,
    duel,
    event,
    farming,
    fishing,
    inventory,
    market,
    mining,
    pet,
    profile,
    ranking,
    shop,
    start,
    work,
)
from utils.logger import logger

app = FastAPI(title="Economy Adventure Bot", version=BOT_VERSION)

application: Application = Application.builder().token(BOT_TOKEN).build()
_application_initialized = False


async def _global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error saat memproses update: %s", context.error)


async def _maintenance_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Group -1: memblokir semua interaksi non-admin jika maintenance mode aktif."""
    if not context.bot_data.get("maintenance_mode"):
        return

    tg_user = update.effective_user
    if tg_user is not None and tg_user.id == ADMIN_ID:
        return

    if update.message is not None:
        await update.message.reply_text("🛠 Bot sedang dalam maintenance. Silakan coba lagi nanti.")
    elif update.callback_query is not None:
        await update.callback_query.answer("🛠 Bot sedang dalam maintenance.", show_alert=True)

    raise ApplicationHandlerStop


def _register_handlers(app_: Application) -> None:
    # Group -1: maintenance gate (dijalankan sebelum semua handler lain)
    app_.add_handler(MessageHandler(filters.ALL, _maintenance_gate), group=-1)
    app_.add_handler(CallbackQueryHandler(_maintenance_gate), group=-1)

    # ---- Command handlers ----
    app_.add_handler(CommandHandler("start", start.start_handler))
    app_.add_handler(CommandHandler("profile", profile.profile_handler))
    app_.add_handler(CommandHandler("work", work.work_handler))
    app_.add_handler(CommandHandler("daily", daily.daily_handler))
    app_.add_handler(CommandHandler("shop", shop.shop_handler))
    app_.add_handler(CommandHandler("inventory", inventory.inventory_handler))
    app_.add_handler(CommandHandler("deposit", bank.deposit_handler))
    app_.add_handler(CommandHandler("withdraw", bank.withdraw_handler))
    app_.add_handler(CommandHandler("bank", bank.bank_handler))
    app_.add_handler(CommandHandler("market", market.market_handler))
    app_.add_handler(CommandHandler("farm", farming.farm_handler))
    app_.add_handler(CommandHandler("fish", fishing.fish_handler))
    app_.add_handler(CommandHandler("mine", mining.mine_handler))
    app_.add_handler(CommandHandler("pet", pet.pet_handler))
    app_.add_handler(CommandHandler("duel", duel.duel_handler))
    app_.add_handler(CommandHandler("ranking", ranking.ranking_handler))
    app_.add_handler(CommandHandler("achievement", achievement.achievement_handler))
    app_.add_handler(CommandHandler("event", event.event_handler))
    app_.add_handler(CommandHandler("admin", admin.admin_handler))
    app_.add_handler(CommandHandler("cancel", admin.admin_cancel_handler))

    # ---- Callback query (inline keyboard) handlers ----
    app_.add_handler(CallbackQueryHandler(start.main_menu_callback, pattern="^menu_main$"))
    app_.add_handler(CallbackQueryHandler(profile.profile_callback, pattern="^menu_profile$"))
    app_.add_handler(CallbackQueryHandler(work.work_callback, pattern="^menu_work$"))
    app_.add_handler(CallbackQueryHandler(daily.daily_callback, pattern="^menu_daily$"))
    app_.add_handler(CallbackQueryHandler(bank.bank_callback, pattern="^menu_bank$"))
    app_.add_handler(CallbackQueryHandler(shop.shop_menu_callback, pattern="^menu_shop$"))
    app_.add_handler(CallbackQueryHandler(shop.buy_callback, pattern="^buy_"))
    app_.add_handler(CallbackQueryHandler(inventory.inventory_callback, pattern="^menu_inventory$"))
    app_.add_handler(CallbackQueryHandler(market.market_callback, pattern="^menu_market$"))
    app_.add_handler(CallbackQueryHandler(farming.farm_menu_callback, pattern="^menu_farm$"))
    app_.add_handler(CallbackQueryHandler(farming.farm_plant_callback, pattern="^farmplant_"))
    app_.add_handler(CallbackQueryHandler(fishing.fish_callback, pattern="^menu_fish$"))
    app_.add_handler(CallbackQueryHandler(mining.mine_callback, pattern="^menu_mine$"))
    app_.add_handler(CallbackQueryHandler(pet.pet_callback, pattern="^menu_pet$"))
    app_.add_handler(CallbackQueryHandler(duel.duel_menu_callback, pattern="^menu_duel$"))
    app_.add_handler(CallbackQueryHandler(ranking.ranking_callback, pattern="^menu_ranking$"))
    app_.add_handler(CallbackQueryHandler(achievement.achievement_callback, pattern="^menu_achievement$"))
    app_.add_handler(CallbackQueryHandler(event.event_callback, pattern="^menu_event$"))
    app_.add_handler(CallbackQueryHandler(admin.admin_menu_callback, pattern="^admin_"))

    # ---- Input teks lanjutan untuk alur admin (harus di grup terpisah agar tidak bentrok) ----
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin.admin_text_handler), group=1)

    app_.add_error_handler(_global_error_handler)


_register_handlers(application)


async def _ensure_initialized() -> None:
    global _application_initialized
    if not _application_initialized:
        await application.initialize()
        _application_initialized = True


@app.post("/api/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Endpoint utama yang menerima update dari Telegram Bot API."""
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Payload webhook tidak valid (bukan JSON).")
        return Response(status_code=400)

    await _ensure_initialized()

    update = Update.de_json(payload, application.bot)
    if update is None:
        return Response(status_code=400)

    try:
        await application.process_update(update)
    except TelegramError:
        logger.exception("Telegram API error saat memproses update.")
    except Exception:
        logger.exception("Kesalahan tak terduga saat memproses update.")

    return Response(status_code=200)


@app.get("/api/webhook")
async def webhook_health_check() -> dict:
    """Health check sederhana - juga berguna untuk memastikan deployment Vercel aktif."""
    return {"status": "ok", "bot": "Economy Adventure Bot", "version": BOT_VERSION}


@app.get("/")
async def root() -> dict:
    return {"status": "running", "service": "Economy Adventure Bot", "version": BOT_VERSION}
