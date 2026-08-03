"""
Handler /duel - PvP sederhana berbasis HP dan random damage.
Cara pakai: balas (reply) pesan pemain lain dengan perintah /duel untuk menantangnya.
"""

import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.settings import DUEL_COOLDOWN_SECONDS
from database.database import get_session
from utils.cooldown import check_cooldown, format_seconds, set_cooldown
from utils.economy import add_coin, add_xp, get_or_create_user, remove_coin

STAKE = 300
DUEL_REWARD = 500
STARTING_HP = 100


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu_main")]])


def _simulate_battle(name_a: str, name_b: str) -> tuple[str, str]:
    """Simulasi battle HP vs HP dengan damage random. Return (nama_pemenang, log_pertarungan)."""
    hp_a, hp_b = STARTING_HP, STARTING_HP
    log_lines = []
    turn = 0

    while hp_a > 0 and hp_b > 0:
        turn += 1
        dmg_a = random.randint(8, 20)
        dmg_b = random.randint(8, 20)
        hp_b -= dmg_a
        if hp_b <= 0:
            log_lines.append(f"Ronde {turn}: {name_a} menyerang {dmg_a} damage. {name_b} kalah!")
            break
        hp_a -= dmg_b
        log_lines.append(f"Ronde {turn}: {name_a} -{dmg_a} HP ke {name_b} | {name_b} -{dmg_b} HP ke {name_a}")
        if hp_a <= 0:
            log_lines.append(f"{name_a} kalah!")
            break

    winner = name_a if hp_a > 0 else name_b
    return winner, "\n".join(log_lines[-3:])  # tampilkan 3 ronde terakhir saja agar ringkas


async def duel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    message = update.message
    if tg_user is None or message is None:
        return

    if message.reply_to_message is None or message.reply_to_message.from_user is None:
        await message.reply_text("⚔️ Balas (reply) pesan pemain lain dengan /duel untuk menantangnya.")
        return

    opponent_tg = message.reply_to_message.from_user
    if opponent_tg.id == tg_user.id:
        await message.reply_text("❌ Kamu tidak bisa menantang diri sendiri.")
        return
    if opponent_tg.is_bot:
        await message.reply_text("❌ Kamu tidak bisa menantang bot.")
        return

    async with get_session() as session:
        challenger, _ = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)

        allowed, remaining = await check_cooldown(session, challenger.id, "duel", DUEL_COOLDOWN_SECONDS)
        if not allowed:
            await message.reply_text(f"⏳ Kamu masih lelah bertarung. Coba lagi dalam {format_seconds(remaining)}.")
            return

        opponent, _ = await get_or_create_user(session, opponent_tg.id, opponent_tg.username, opponent_tg.full_name)

        if challenger.coin < STAKE or opponent.coin < STAKE:
            await message.reply_text(f"❌ Kedua pemain butuh minimal 💰 {STAKE} coin untuk duel.")
            return

        challenger_name = challenger.full_name or tg_user.first_name
        opponent_name = opponent.full_name or opponent_tg.first_name

        winner_name, battle_log = _simulate_battle(challenger_name, opponent_name)

        await remove_coin(challenger, STAKE)
        await remove_coin(opponent, STAKE)

        prize = STAKE * 2 + DUEL_REWARD

        if winner_name == challenger_name:
            await add_coin(challenger, prize)
            await add_xp(challenger, 80)
            challenger.total_fight += 1
        else:
            await add_coin(opponent, prize)
            await add_xp(opponent, 80)
            opponent.total_fight += 1

        await set_cooldown(session, challenger.id, "duel")

        text = (
            f"⚔️ {challenger_name} VS {opponent_name}\n\n"
            f"{battle_log}\n\n"
            f"🏆 Pemenang: {winner_name}\n"
            f"💰 Hadiah: {prize} Coin"
        )

    await message.reply_text(text, reply_markup=_back_button())


async def duel_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    await query.edit_message_text(
        "⚔️ Duel\n\nBalas (reply) pesan pemain lain dengan perintah /duel untuk menantangnya.",
        reply_markup=_back_button(),
    )
