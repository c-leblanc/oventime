from contextlib import asynccontextmanager, suppress
import asyncio
import uvicorn

from oventime.jobs.orchestrator import orchestrator_loop
from oventime.api.routes import app


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
