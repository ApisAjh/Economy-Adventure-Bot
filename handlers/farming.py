"""
Handler /farm - menanam dan memanen tanaman.

Format:
/farm plant <Jagung|Gandum|Padi>
/farm harvest
/farm status
"""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.database import get_session
from database.models import Farming
from utils.cooldown import format_seconds
from utils.economy import add_coin, add_xp, get_or_create_user
from utils.items import PLANTS


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


def _plant_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(f"{d['emoji']} {name}", callback_data=f"farmplant_{name}")] for name, d in PLANTS.items()]
    buttons.append([InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)


async def _get_active_farm(session, user_id: int) -> Farming | None:
    result = await session.execute(
        select(Farming).where(Farming.user_id == user_id, Farming.status.in_(["growing", "ready"]))
    )
    return result.scalar_one_or_none()


async def farm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user is None or update.message is None:
        return

    args = context.args or []

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        active = await _get_active_farm(session, user.id)

        if not args or args[0].lower() == "status":
            if active is None:
                await update.message.reply_text(
                    "🌾 Kamu belum menanam apa-apa.\nPilih tanaman untuk mulai bertani:",
                    reply_markup=_plant_keyboard(),
                )
                return

            now = datetime.now(timezone.utc)
            harvest_time = active.harvest_time
            if harvest_time.tzinfo is None:
                harvest_time = harvest_time.replace(tzinfo=timezone.utc)

            if now >= harvest_time and active.status == "growing":
                active.status = "ready"

            if active.status == "ready":
                await update.message.reply_text(
                    f"🌱 {active.plant} sudah siap dipanen!\nGunakan /farm harvest",
                    reply_markup=_back_button(),
                )
            else:
                remaining = int((harvest_time - now).total_seconds())
                await update.message.reply_text(
                    f"🌱 {active.plant} masih tumbuh.\nSiap panen dalam {format_seconds(remaining)}.",
                    reply_markup=_back_button(),
                )
            return

        if args[0].lower() == "plant":
            if active is not None:
                await update.message.reply_text("❌ Kamu sudah punya tanaman aktif. Panen dulu sebelum menanam lagi.")
                return

            if len(args) < 2 or args[1].capitalize() not in PLANTS:
                await update.message.reply_text("Pilih tanaman: Jagung, Gandum, atau Padi.\nContoh: /farm plant Jagung")
                return

            await _plant(session, user.id, args[1].capitalize())
            plant_def = PLANTS[args[1].capitalize()]
            await update.message.reply_text(
                f"{plant_def['emoji']} Kamu menanam {args[1].capitalize()}!\n"
                f"Siap panen dalam {format_seconds(plant_def['grow_seconds'])}.",
                reply_markup=_back_button(),
            )
            return

        if args[0].lower() == "harvest":
            text = await _harvest(session, user)
            await update.message.reply_text(text, reply_markup=_back_button())
            return

        await update.message.reply_text("Perintah tidak dikenali. Gunakan /farm plant, /farm harvest, atau /farm status.")


async def _plant(session, user_id: int, plant_name: str) -> Farming:
    plant_def = PLANTS[plant_name]
    now = datetime.now(timezone.utc)
    harvest_time = now + timedelta(seconds=plant_def["grow_seconds"])
    amount = random.randint(plant_def["yield_min"], plant_def["yield_max"])

    farm = Farming(
        user_id=user_id,
        plant=plant_name,
        amount=amount,
        plant_time=now,
        harvest_time=harvest_time,
        status="growing",
    )
    session.add(farm)
    await session.flush()
    return farm


async def _harvest(session, user) -> str:
    active = await _get_active_farm(session, user.id)
    if active is None:
        return "❌ Kamu tidak punya tanaman untuk dipanen."

    now = datetime.now(timezone.utc)
    harvest_time = active.harvest_time
    if harvest_time.tzinfo is None:
        harvest_time = harvest_time.replace(tzinfo=timezone.utc)

    if now < harvest_time:
        remaining = int((harvest_time - now).total_seconds())
        return f"⏳ Belum siap panen. Tunggu {format_seconds(remaining)} lagi."

    plant_def = PLANTS[active.plant]
    coin_reward = active.amount * plant_def["sell_price"]

    await add_coin(user, coin_reward)
    await add_xp(user, active.amount * 10)
    active.status = "harvested"

    return (
        f"🌾 Panen berhasil!\n\n"
        f"{plant_def['emoji']} {active.plant} x{active.amount}\n"
        f"💰 +{coin_reward} Coin"
    )


async def farm_plant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None or query.data is None:
        return
    await query.answer()

    plant_name = query.data.removeprefix("farmplant_")
    if plant_name not in PLANTS:
        return

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        active = await _get_active_farm(session, user.id)

        if active is not None:
            await query.edit_message_text("❌ Kamu sudah punya tanaman aktif. Panen dulu sebelum menanam lagi.", reply_markup=_back_button())
            return

        await _plant(session, user.id, plant_name)
        plant_def = PLANTS[plant_name]

    await query.edit_message_text(
        f"{plant_def['emoji']} Kamu menanam {plant_name}!\nSiap panen dalam {format_seconds(plant_def['grow_seconds'])}.",
        reply_markup=_back_button(),
    )


async def farm_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    async with get_session() as session:
        user, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
        active = await _get_active_farm(session, user.id)

    if active is None:
        await query.edit_message_text("🌾 Pilih tanaman untuk mulai bertani:", reply_markup=_plant_keyboard())
    else:
        await query.edit_message_text(
            f"🌱 Kamu sedang menanam {active.plant}.\nGunakan /farm status atau /farm harvest.",
            reply_markup=_back_button(),
        )
