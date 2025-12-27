import logging
from telegram.ext import ContextTypes
import httpx
import asyncio

from oventime.interfaces.messaging import msg_diagnostic, msg_price_window
from oventime.config import (
    LEAF_THRESHOLD, FIRE_THRESHOLD, WINDOW_METHOD, OTSU_SEVERITY,
    API_BASE_URL)

logging.basicConfig(level=logging.INFO)


async def now(update, context):
    """Répond avec le diagnostic actuel."""
    msg = msg_diagnostic()
    await update.message.reply_text(msg, parse_mode="Markdown")

async def at(update, context):
    """Répond avec le diagnostic à l'heure demandée en supposant Europe/Paris puis converti en UTC."""
    if not context.args:
        await update.message.reply_text(
            "Veuillez préciser une heure après /a (ex: /a 15:30, /a 9am, /a hier 9am)", 
            parse_mode="Markdown"
        )
        return

    time_str = " ".join(context.args)

    try:
        msg = msg_diagnostic(at_time=time_str)
    except ValueError as e:
        await update.message.reply_text(str(e), parse_mode="Markdown")
        return
    except Exception as e:
        await update.message.reply_text(f"Erreur lors du calcul du diagnostic", parse_mode="Markdown")
        return
    await update.message.reply_text(msg, parse_mode="Markdown")

async def window(update, context):
    """Répond avec la meilleure fenêtre à venir."""
    msg = msg_price_window()
    await update.message.reply_text(msg, parse_mode="Markdown")


#############################################
## AUTOMATIC ALERT MESSAGES

SUBSCRIBERS_KEY = "subscribers"

async def start_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.add(chat_id)
    print(f"Subscriber to automatic messages added: {chat_id}. (Total={len(subscribers)} active subscribers)")
    await update.message.reply_text("✅ ACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡ ou de forte tension sur le réseau 🔥🏭")

async def stop_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.discard(chat_id)
    print("Subscriber to automatic messages removed: {chat_id}. (Total={len(subscribers)} active subscribers)")
    await update.message.reply_text("❌ INACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡ ou de forte tension sur le réseau 🔥🏭")


async def check_score_job(application):
    print("[check_score_job called]")
    last_seen_ts = application.bot_data.get("last_seen_ts")

    async with httpx.AsyncClient(timeout=2) as client:
        r = await client.get(f"{API_BASE_URL}/diagnostic")
        r.raise_for_status()
        diag = r.json()

    if diag is None:
        return

    ts = diag["ts"]

    # 👉 Rien de nouveau
    if ts == last_seen_ts:
        return

    application.bot_data["last_seen_ts"] = ts

    score = diag["score"]
    subscribers = application.bot_data.get(SUBSCRIBERS_KEY, set())

    state_high = application.bot_data.setdefault("last_alert_high", False)
    state_low = application.bot_data.setdefault("last_alert_low", False)

    text = None

    if score <= LEAF_THRESHOLD and state_high:
        text = "❌ Fin de la période d'abondance ⚡🍃"
        application.bot_data["last_alert_high"] = False

    elif score >= FIRE_THRESHOLD and state_low:
        text = "✅ Fin de la période de forte tension 🔥🏭"
        application.bot_data["last_alert_low"] = False

    elif score > LEAF_THRESHOLD and not state_high:
        text = (
            "🍃⚡ ABONDANCE ⚡🍃\n"
            "Il y a un surplus d'électricité décarbonée sur le réseau !\n"
            f"(Score : {score:.0f}, /m pour plus d'infos)"
        )
        application.bot_data["last_alert_high"] = True

    elif score < FIRE_THRESHOLD and not state_low:
        text = (
            "🔥🏭 FORTE TENSION 🔥🏭\n"
            "L'électricité se fait rare et on a démarré les centrales les plus polluantes !\n"
            f"(Score : {score:.0f}, /m pour plus d'infos)"
        )
        application.bot_data["last_alert_low"] = True

    if text is not None:
        for chat_id in subscribers:
            await application.bot.send_message(chat_id=chat_id, text=text)




        


