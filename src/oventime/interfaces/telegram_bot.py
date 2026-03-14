import logging
from telegram.ext import ContextTypes
import httpx

logger = logging.getLogger(__name__)

from oventime.interfaces.messaging import msg_diagnostic, msg_price_window
from oventime.config import (API_BASE_URL, INTERNAL_API_TOKEN)

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
        await update.message.reply_text(f"Donnée non disponible", parse_mode="Markdown")
        return
    await update.message.reply_text(msg, parse_mode="Markdown")

async def window(update, context):
    """Répond avec la meilleure fenêtre à venir."""
    msg = msg_price_window()
    await update.message.reply_text(msg, parse_mode="Markdown")


#############################################
## AUTOMATIC ALERT MESSAGES

async def start_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"{API_BASE_URL}/tsubs/{chat_id}",
                headers = {"x-internal-token": INTERNAL_API_TOKEN}
                )
            r.raise_for_status()
    except Exception:
        await update.message.reply_text("⚠️ Erreur lors de l'inscription, réessaie plus tard.")
        return    
    logger.info(f"Telegram subscriber added: {chat_id}.")
    await update.message.reply_text("✅ ACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡ ou de forte tension sur le réseau 🔥🏭")


async def stop_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.delete(
                f"{API_BASE_URL}/tsubs/{chat_id}",
                headers={"x-internal-token": INTERNAL_API_TOKEN}
                )
            r.raise_for_status()
    except Exception:
        await update.message.reply_text("⚠️ Erreur lors de la désinscription, réessaie plus tard.")
        return 
    logger.info(f"Telegram subscriber deactivated: {chat_id}.")
    await update.message.reply_text("❌ INACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡ ou de forte tension sur le réseau 🔥🏭")


