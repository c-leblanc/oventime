from contextlib import asynccontextmanager, suppress
import asyncio
import sys
import logging
import uvicorn

from telegram.ext import ApplicationBuilder, CommandHandler

from oventime.jobs.orchestrator import orchestrator_loop
from oventime.api.routes import app
from oventime.config import TELEGRAM_TOKEN
from oventime.interfaces.telegram_bot import now, at, window, start_auto, stop_auto

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, handlers=[stdout_handler, stderr_handler])


@asynccontextmanager
async def lifespan(app):
    # ── Bot Telegram ──
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("m", now))
    bot_app.add_handler(CommandHandler("a", at))
    bot_app.add_handler(CommandHandler("q", window))
    bot_app.add_handler(CommandHandler("start_auto", start_auto))
    bot_app.add_handler(CommandHandler("stop_auto", stop_auto))

    if TELEGRAM_TOKEN:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()

    # ── Orchestrateur ──
    orch_task = asyncio.create_task(orchestrator_loop())

    yield

    # ── Shutdown ──
    orch_task.cancel()
    with suppress(asyncio.CancelledError):
        await orch_task

    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080
    )