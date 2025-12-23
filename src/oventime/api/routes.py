from fastapi import FastAPI

import oventime.core.decision as decision

app = FastAPI()

@app.get("/status/now")
def status_now():
    return decision.diagnostic()