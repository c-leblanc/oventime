from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from oventime.cache.cache import (
    get_status,
    get_fulldiag,
    get_nextwindow
)



app = FastAPI(
    title="Oventime API",
    version="0.1",
    description="API read-only pour l'état du système électrique"
)


@app.get("/status/now")
def status_now():
    """
    Statut courant (léger, pour bot / widget)
    """
    res = get_status()
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return res


@app.get("/diagnostic/now")
def diagnostic_now():
    """
    Diagnostic complet courant
    """
    res = get_fulldiag()
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return res


@app.get("/diagnostic/at")
def diagnostic_at(time: str):
    """
    Diagnostic à un instant donné
    """
    res = get_fulldiag(target_time=time)
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return res


@app.get("/next/window")
def next_window():
    """
    Diagnostic complet courant
    """
    res = get_nextwindow()
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return res



