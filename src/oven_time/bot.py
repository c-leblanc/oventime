import logging
import pandas as pd
import dateparser
from telegram.ext import ApplicationBuilder, CommandHandler
from oven_time.core import get_diagnostic

TOKEN = "8590705995:AAHrgVVWuk3KyxxS7aHcz0Po8o0222QERfY"

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

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("m", now))
    app.add_handler(CommandHandler("a", at))
    app.run_polling()

if __name__ == "__main__":
    main()