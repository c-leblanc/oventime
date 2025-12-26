import sys
from pathlib import Path
from telegram.ext import ApplicationBuilder, CommandHandler
from oventime.interfaces.telegram_bot import check_score_job


# Ajouter src au PYTHONPATH
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from oventime.config import TELEGRAM_TOKEN
from oventime.interfaces.telegram_bot import *


def main():
    
    #Launch the bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("m", now))
    app.add_handler(CommandHandler("a", at))
    app.add_handler(CommandHandler("q", window))
    app.add_handler(CommandHandler("start_auto", start_auto))
    app.add_handler(CommandHandler("stop_auto", stop_auto))

    app.job_queue.run_repeating(
        check_score_job,
        interval=60,   # secondes
        first=10       # attendre 10s après le démarrage
        )

    app.run_polling()

if __name__ == "__main__":
    main()

