from contextlib import asynccontextmanager, suppress
import asyncio
import sys
import logging
import uvicorn

from oventime.jobs.orchestrator import orchestrator_loop
from oventime.api.routes import app

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, handlers=[stdout_handler, stderr_handler])

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
        port=8080
    )

