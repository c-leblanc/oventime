import logging
import pandas as pd
import dateparser
import threading
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from oven_time.core import get_diagnostic
from oven_time.api_eco2mix import background_updater
from oven_time.config import TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO)

async def now(update, context):
    """Répond avec le diagnostic actuel."""
    msg = get_diagnostic()
    await update.message.reply_markdown(msg)

async def at(update, context):
    """Répond avec le diagnostic à l'heure demandée en supposant Europe/Paris puis converti en UTC."""
    if not context.args:
        await update.message.reply_text(
            "Veuillez préciser une heure après /a (ex: /a 15:30, /a 9am, /a hier 9am)"
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
        dt = pd.Timestamp(dt)

        # convertir en UTC
        dt_utc = dt.tz_convert("UTC")

    except Exception:
        await update.message.reply_text(
            f"Format d'heure invalide : {time_str}\nExemples valides : 9, 9am, 21:30, hier 9am, demain 14h"
        )
        return

    # appeler votre diagnostic
    msg = get_diagnostic(at_time=dt_utc)
    await update.message.reply_markdown(msg)

#############################################
## AUTOMATIC ALERT MESSAGES

SUBSCRIBERS_KEY = "subscribers"

async def start_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.add(chat_id)
    await update.message.reply_text("✅ ACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡")

async def stop_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.discard(chat_id)
    await update.message.reply_text("❌ INACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡")

async def check_score_job(context: ContextTypes.DEFAULT_TYPE):
    global last_alert_high
    diag = get_diagnostic()
    score = diag.get("score", 0)

    subscribers = context.application.bot_data.get(SUBSCRIBERS_KEY, set())

    if score > 100 and not last_alert_high:
        text = (
            "ALERTE FOURNIL !\n\n"
            f"Score actuel : {score}\n"
            "A FOND! Y a de l'électricité à ne savoir qu'en faire."
        )
        for chat_id in subscribers:
            await context.bot.send_message(chat_id=chat_id, text=text)
        last_alert_high = True
    elif score <= 100 and last_alert_high:
        last_alert_high = False

async def on_startup(app):
    # job toutes les 5 minutes (par ex.)
    app.job_queue.run_repeating(
        check_score_job,
        interval=300,
        first=10,  # démarre 10 s après le lancement
    )


def main():
    # Launch regular updates
    t = threading.Thread(target=background_updater, daemon=True)
    t.start()

    #Launch the bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("m", now))
    app.add_handler(CommandHandler("a", at))
    app.add_handler(CommandHandler("start_auto", start_auto))
    app.add_handler(CommandHandler("stop_auto", stop_auto))
    app.run_polling()

if __name__ == "__main__":
    main()