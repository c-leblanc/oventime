import logging
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3

logger = logging.getLogger(__name__)

from oventime.cache.cache import (
    get_status,get_fulldiag,get_nextwindow,get_timeline,
    add_wsubs,remove_wsubs,
    get_connection
)
from oventime.jobs.notifier import notifier
from oventime.config import INTERNAL_API_TOKEN, VAPID_PUBLIC_KEY

ALLOWED_TABLES = {"cache", "web_subscribers", "timeline"}


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

@app.get("/prices/timeline")
def prices_timeline():
    """Timeline ternaire (vert/orange/rouge) des prochaines heures."""
    slots = get_timeline()
    if not slots:
        raise HTTPException(status_code=404, detail="No timeline available")
    return {"slots": slots}


# ─────────────────────────────────────────────
# Web Push subscribers
 
@app.get("/vapid-public-key")
def vapid_public_key():
    return {"publicKey": VAPID_PUBLIC_KEY}
 
 
@app.post("/wsubs", status_code=201)
async def add_web_subscription(request: Request):
    body = await request.json()
    endpoint = body.get("endpoint")
    if not endpoint or "keys" not in body:
        raise HTTPException(status_code=400, detail="Subscription invalide")
    add_wsubs(endpoint, body)
    try:
        await notifier._notify_web(
            title="OvenTime ⚡",
            body="✅ Alertes activées — tu recevras une notif en cas d'abondance 🍃 ou de forte tension 🔥",
            subs_override={endpoint: body}
        )
    except Exception as e:
        logger.error(f"Erreur notif confirmation: {e!r}")
    return {"status": "subscribed"}
 
@app.delete("/wsubs", status_code=200)
async def remove_web_subscription(request: Request):
    body = await request.json()
    remove_wsubs(body.get("endpoint", ""))
    return {"status": "unsubscribed"}
 

@app.delete("/admin/wsubs/all")
def clear_all_wsubs(x_internal_token: str | None = Header(default=None)):
    _check_token(x_internal_token)
    conn = get_connection()
    conn.execute("DELETE FROM web_subscribers")
    conn.commit()
    conn.close()
    return {"status": "cleared"}
 

# ─────────────────────────────────────────────
# Admin / debug

@app.get("/admin/tables")
def list_tables(x_internal_token: str | None = Header(default=None)):
    """Liste toutes les tables de la base."""
    _check_token(x_internal_token)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return {"tables": tables}


@app.get("/admin/tables/{table_name}")
def view_table(table_name: str, x_internal_token: str | None = Header(default=None)):
    """Retourne le contenu complet d'une table."""
    _check_token(x_internal_token)
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="Table inconnue")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        conn.close()
    return {"table": table_name, "count": len(rows), "rows": rows}


# ─────────────────────────────────────────────


app.mount("/static", StaticFiles(directory="src/oventime/api/static"), name="static")

@app.get("/sw.js")
def service_worker():
    return FileResponse("src/oventime/api/static/sw.js", media_type="application/javascript")

@app.get("/")
def index():
    return FileResponse("src/oventime/api/static/index.html")

