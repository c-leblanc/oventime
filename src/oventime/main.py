from contextlib import asynccontextmanager, suppress
import asyncio
import sys
import logging
import uvicorn

from oventime.jobs.orchestrator import orchestrator_loop
from oventime.api.routes import app


logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    # startup
    task = asyncio.create_task(orchestrator_loop())

    yield

    # shutdown
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["default"], "level": "INFO"},
        }
    )

