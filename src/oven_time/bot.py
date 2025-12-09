import logging
from pandas import Timestamp
import dateparser
import threading
import time
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from oven_time.core import get_diagnostic
from oven_time.decision import diagnostic
from oven_time.api_eco2mix import update_eco2mix_data
from oven_time.config import TELEGRAM_TOKEN, RETENTION_DAYS, FREQ_UPDATE

logging.basicConfig(level=logging.INFO)


async def now(update, context):
    """Répond avec le diagnostic actuel."""
    msg = get_diagnostic()
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
        # parser avec dateparser pour plus de flexibilité
        dt = dateparser.parse(
            time_str,
            settings={
                'TIMEZONE': 'Europe/Paris',
                'RETURN_AS_TIMEZONE_AWARE': True,
                'PREFER_DATES_FROM': 'past',  # ou 'future' selon vos besoins
            }
        )

        if dt is None:
            raise ValueError("Impossible d'interpréter la date/heure.")

        # convertir en Timestamp pandas
        dt = Timestamp(dt)

        # convertir en UTC
        dt_utc = dt.tz_convert("UTC")

    except Exception:
        await update.message.reply_text(
            f"Format d'heure invalide : {time_str}\nExemples valides : 9, 9am, 21:30, hier 9am, demain 14h"
        )
        return

    # appeler votre diagnostic
    msg = get_diagnostic(at_time=dt_utc)
    await update.message.reply_text(msg, parse_mode="Markdown")

#############################################
## AUTOMATIC ALERT MESSAGES

SUBSCRIBERS_KEY = "subscribers"

async def start_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.add(chat_id)
    print("Subscriber to automatic messages added.")
    await update.message.reply_text("✅ ACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡")

async def stop_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.discard(chat_id)
    print("Subscriber to automatic messages removed.")
    await update.message.reply_text("❌ INACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡")



async def check_score_job(application):
    state = application.bot_data.setdefault("last_alert_high", False)
    print(f"Last alert high ? {state}")
    diag = diagnostic()
    score = diag["score"]
    subscribers = application.bot_data.get(SUBSCRIBERS_KEY, set())

    if score > 100 and not state:
        text = f"🍃⚡ ABONDANCE ⚡🍃\nIl y a un surplus d'électricité décarbonée sur le réseau !\n(Score : {score:.0f}, /m for more info)"
        for chat_id in subscribers:
            await application.bot.send_message(chat_id=chat_id, text=text)
        application.bot_data["last_alert_high"] = True
    elif score <= 100 and state:
        application.bot_data["last_alert_high"] = False


async def background_job(application, retention_days=RETENTION_DAYS, freq=FREQ_UPDATE):
    """
    Coroutine qui tourne en boucle infinie pour :
    1. mettre à jour eco2mix
    2. lancer check_score_job après chaque update
    """
    while True:
        await asyncio.sleep(freq * 60)

        update_eco2mix_data(retention_days=retention_days, verbose=True)
        await check_score_job(application)

        


async def on_startup(application):
    application.create_task(background_job(application))


def main():
    
    #Launch the bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("m", now))
    app.add_handler(CommandHandler("a", at))
    app.add_handler(CommandHandler("start_auto", start_auto))
    app.add_handler(CommandHandler("stop_auto", stop_auto))

    # enregistrement du callback de startup
    app.post_init = on_startup

    app.run_polling()

if __name__ == "__main__":
    main()