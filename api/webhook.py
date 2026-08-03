"""
Entry point webhook Telegram untuk Vercel Serverless.

Menggunakan:
- FastAPI
- python-telegram-bot async
- Telegram Webhook
- Tanpa polling
"""

import sys
from pathlib import Path

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


from config.settings import (
    ADMIN_ID,
    BOT_TOKEN,
    BOT_VERSION,
)


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


app = FastAPI(
    title="Economy Adventure Bot",
    version=BOT_VERSION
)


application = (
    Application
    .builder()
    .token(BOT_TOKEN)
    .build()
)


_initialized = False
_started = False

async def _global_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    logger.exception(
        "Unhandled error saat memproses update: %s",
        context.error
    )


async def _maintenance_gate(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Middleware maintenance.
    Group -1 agar jalan sebelum handler lain.
    """

    if not context.bot_data.get("maintenance_mode"):
        return


    user = update.effective_user

    if user and user.id == ADMIN_ID:
        return


    if update.message:
        await update.message.reply_text(
            "🛠 Bot sedang maintenance. Coba lagi nanti."
        )


    elif update.callback_query:
        await update.callback_query.answer(
            "🛠 Bot sedang maintenance.",
            show_alert=True
        )


    raise ApplicationHandlerStop



def _register_handlers(app_: Application):

    # Maintenance middleware
    app_.add_handler(
        MessageHandler(
            filters.ALL,
            _maintenance_gate
        ),
        group=-1
    )


    app_.add_handler(
        CallbackQueryHandler(
            _maintenance_gate
        ),
        group=-1
    )



    # ======================
    # COMMAND HANDLER
    # ======================

    commands = [
        ("start", start.start_handler),
        ("profile", profile.profile_handler),
        ("work", work.work_handler),
        ("daily", daily.daily_handler),
        ("shop", shop.shop_handler),
        ("inventory", inventory.inventory_handler),
        ("deposit", bank.deposit_handler),
        ("withdraw", bank.withdraw_handler),
        ("bank", bank.bank_handler),
        ("market", market.market_handler),
        ("farm", farming.farm_handler),
        ("fish", fishing.fish_handler),
        ("mine", mining.mine_handler),
        ("pet", pet.pet_handler),
        ("duel", duel.duel_handler),
        ("ranking", ranking.ranking_callback),
        ("achievement", achievement.achievement_handler),
        ("event", event.event_handler),
        ("admin", admin.admin_handler),
        ("cancel", admin.admin_cancel_handler),
    ]


    for command, handler in commands:
        app_.add_handler(
            CommandHandler(
                command,
                handler
            )
        )



    # ======================
    # CALLBACK HANDLER
    # ======================

    callbacks = [
        ("^menu_main$", start.main_menu_callback),
        ("^menu_profile$", profile.profile_callback),
        ("^menu_work$", work.work_callback),
        ("^menu_daily$", daily.daily_callback),
        ("^menu_bank$", bank.bank_callback),
        ("^menu_shop$", shop.shop_menu_callback),
        ("^buy_", shop.buy_callback),
        ("^menu_inventory$", inventory.inventory_callback),
        ("^menu_market$", market.market_callback),
        ("^menu_farm$", farming.farm_menu_callback),
        ("^farmplant_", farming.farm_plant_callback),
        ("^menu_fish$", fishing.fish_callback),
        ("^menu_mine$", mining.mine_callback),
        ("^menu_pet$", pet.pet_callback),
        ("^menu_duel$", duel.duel_menu_callback),
        ("^menu_ranking$", ranking.ranking_callback),
        ("^menu_achievement$", achievement.achievement_callback),
        ("^menu_event$", event.event_callback),
        ("^admin_", admin.admin_menu_callback),
    ]


    for pattern, handler in callbacks:
        app_.add_handler(
            CallbackQueryHandler(
                handler,
                pattern=pattern
            )
        )



    # Text handler admin
    app_.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.admin_text_handler
        ),
        group=1
    )


    app_.add_error_handler(
        _global_error_handler
    )



_register_handlers(application)

async def _ensure_application():
    """
    Lifecycle aman untuk Vercel Serverless.

    PTB butuh:
    initialize()
    start()

    Tidak memakai polling.
    """

    global _initialized
    global _started


    if not _initialized:
        await application.initialize()

        _initialized = True

        logger.info(
            "Telegram Application initialized."
        )


    if not _started:
        await application.start()

        _started = True

        logger.info(
            "Telegram Application started."
        )



@app.post("/api/webhook")
async def telegram_webhook(
    request: Request
) -> Response:

    try:
        payload = await request.json()

    except Exception:
        logger.warning(
            "Webhook payload bukan JSON."
        )

        return Response(
            status_code=400
        )


    try:

        await _ensure_application()


        update = Update.de_json(
            payload,
            application.bot
        )


        if update is None:
            return Response(
                status_code=400
            )


        await application.process_update(
            update
        )


    except TelegramError:
        logger.exception(
            "Telegram API error."
        )


    except Exception:
        logger.exception(
            "Error saat process update."
        )


    return Response(
        status_code=200
    )



@app.get("/api/webhook")
async def webhook_health_check():

    return {
        "status": "ok",
        "bot": "Economy Adventure Bot",
        "version": BOT_VERSION
    }



@app.get("/")
async def root():

    return {
        "status": "running",
        "service": "Economy Adventure Bot",
        "version": BOT_VERSION
    }
