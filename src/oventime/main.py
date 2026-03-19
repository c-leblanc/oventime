from contextlib import asynccontextmanager, suppress
import asyncio
import sys
import logging
import uvicorn

from oventime.jobs.orchestrator import orchestrator_loop
from oventime.api.routes import app
from oventime.config import FORCE_RAW_REFRESH
from oventime.input.data_storage import RAW_DB_PATH

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, handlers=[stdout_handler, stderr_handler])


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    # ── Force raw data refresh ──
    if FORCE_RAW_REFRESH and RAW_DB_PATH.exists():
        RAW_DB_PATH.unlink()
        logger.info("raw.sqlite supprimé (FORCE_RAW_REFRESH=True). Re-téléchargement au prochain cycle.")

    # ── Orchestrateur ──
    orch_task = asyncio.create_task(orchestrator_loop())

    yield

    # ── Shutdown ──
    orch_task.cancel()
    with suppress(asyncio.CancelledError):
        await orch_task


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080
    )
