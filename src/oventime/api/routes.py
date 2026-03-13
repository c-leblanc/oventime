from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os


from oventime.cache.cache import (
    get_status,get_fulldiag,get_nextwindow,
    get_wsubs,add_wsubs,remove_wsubs,
    get_tsubs,add_tsubs,remove_tsubs
)

from oventime.config import INTERNAL_API_TOKEN


app = FastAPI(
    title="Oventime API",
    version="0.1",
    description="API read-only pour l'état du système électrique"
)


def _check_token(token: str | None):
    if not INTERNAL_API_TOKEN or token != INTERNAL_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/status")
def status(time: str = None):
    """
    API Request -- Status only for latest available timestamp or other timestamp if specified.
    
    :param time: Time at which the status is requested (latest available if None).
    :type time: str
    """
    res = get_status(target_time=time)
    if res is None:
        raise HTTPException(status_code=404, detail="No status available")

    return res



@app.get("/diagnostic")
def diagnostic(time: str = None):
    """
    API Request -- Full diagnostic for latest available timestamp or other timestamp if specified.
    
    :param time: Time at which the diagnostic is requested (latest available if None).
    :type time: str
    """
    res = get_fulldiag(target_time=time)
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return res


@app.get("/next/window")
def next_window(time: str = None):
    """
    API Request -- Next window with low prices (anticipated at <time>).
    
    :param time: Time (latest available if None).
    :type time: str
    """
    res = get_nextwindow(time)
    if res is None:
        raise HTTPException(status_code=404, detail="No estimates available for the next window")

    return res

# ─────────────────────────────────────────────
# Web Push subscribers

@app.get("/vapid-public-key")
def vapid_public_key():
    return {"publicKey": os.environ["VAPID_PUBLIC_KEY"]}

@app.post("/wsubs", status_code=201)
async def add_web_subscription(request: Request):
    body = await request.json()
    endpoint = body.get("endpoint")
    if not endpoint or "keys" not in body:
        raise HTTPException(status_code=400, detail="Subscription invalide")
    add_wsubs(endpoint, body)
    return {"status": "subscribed"}

@app.delete("/wsubs", status_code=200)
async def remove_web_subscription(request: Request):
    body = await request.json()
    remove_wsubs(body.get("endpoint", ""))
    return {"status": "unsubscribed"}

class NotifyRequest(BaseModel):
    title: str
    body: str

@app.post("/wsubs/notify", status_code=200)
async def notify_web(payload: NotifyRequest, x_internal_token: str | None = Header(default=None)):
    _check_token(x_internal_token)
    await _send_to_all_wsubs(payload.title, payload.body)
    return {"status": "sent"}

# ─────────────────────────────────────────────
# Telegram subscribers

@app.get("/tsubs")
def list_tsubs(x_internal_token: str | None = Header(default=None)):
    """Retourne la liste des chat_id abonnés actifs."""
    _check_token(x_internal_token)
    subs = get_tsubs()
    return {"chat_ids": list(subs)}


@app.post("/tsubs/{chat_id}", status_code=200)
def subscribe(chat_id: int, x_internal_token: str | None = Header(default=None)):
    """Active (ou réactive) un abonné."""
    _check_token(x_internal_token)
    add_tsubs(chat_id)
    return {"status": "subscribed", "chat_id": chat_id}


@app.delete("/tsubs/{chat_id}", status_code=200)
def unsubscribe(chat_id: int, x_internal_token: str | None = Header(default=None)):
    """Désactive un abonné."""
    _check_token(x_internal_token)
    remove_tsubs(chat_id)
    return {"status": "unsubscribed", "chat_id": chat_id}


# ─────────────────────────────────────────────



app.mount("/static", StaticFiles(directory="src/oventime/api/static"), name="static")

@app.get("/")
def index():
    return FileResponse("src/oventime/api/static/index.html")

