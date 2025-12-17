import sys
from pathlib import Path
from telegram.ext import ApplicationBuilder, CommandHandler

# Ajouter src au PYTHONPATH
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from oven_time.config import TELEGRAM_TOKEN
from oven_time.bot_commands import *

async def on_startup(application):
    application.create_task(background_job(application))


def main():
    
    #Launch the bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("m", now))
    app.add_handler(CommandHandler("a", at))
    app.add_handler(CommandHandler("q", window))
    app.add_handler(CommandHandler("start_auto", start_auto))
    app.add_handler(CommandHandler("stop_auto", stop_auto))

    # enregistrement du callback de startup
    app.post_init = on_startup

    app.run_polling()

if __name__ == "__main__":
    main()

