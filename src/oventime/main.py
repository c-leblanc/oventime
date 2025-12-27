import threading
import uvicorn

from oventime.jobs.orchestrator import orchestrator_loop
# l'app FastAPI
from oventime.api.routes import app



if __name__ == "__main__":
    threading.Thread(target=orchestrator_loop, daemon=True).start()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080
    )
