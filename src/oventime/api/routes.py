from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from oventime.cache.diagnostic import (
    get_status_now,
    get_fulldiag,
)
from oventime.cache.dayahead import (
    get_nextwindow
)
from oventime.utils import to_utc_timestamp
from oventime.config import TIMEZONE


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
    res = get_status_now()
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return {
        "time": to_utc_timestamp(res["ts"]).tz_convert(tz=TIMEZONE).isoformat(),
        "status": res["status"],
    }


@app.get("/diagnostic/now")
def diagnostic_now():
    """
    Diagnostic complet courant
    """
    res = get_fulldiag()
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return _format_full_diagnostic(res)


@app.get("/diagnostic/at")
def diagnostic_at(time: str):
    """
    Diagnostic à un instant donné
    """
    res = get_fulldiag(target_time=time)
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return _format_full_diagnostic(res)


@app.get("/next/window")
def next_window():
    """
    Diagnostic complet courant
    """
    res = get_nextwindow()
    if res is None:
        raise HTTPException(status_code=404, detail="No diagnostic available")

    return _format_full_diagnostic(res)


# ----------------------------
# Helpers internes API
# ----------------------------

def _format_full_diagnostic(d):
    return {
        "time": to_utc_timestamp(d["ts"]).tz_convert(tz=TIMEZONE).isoformat(),
        "status": d["status"],
        "score": d["score"],
        "details": {
            "gasCCG_use_rate": d["gasCCG_use_rate"],
            "storage_phase": d["storage_phase"],
            "storage_use_rate": d["storage_use_rate"],
            "nuclear_use_rate": d["nuclear_use_rate"],
            "nuclear_bonus": d["nuclear_bonus"],
            "ocgt_malus": d["ocgt_malus"],
        },
        "meta": {
            "source_version": d["source_version"],
            "created_at": to_utc_timestamp(d["created_at"]).tz_convert(tz=TIMEZONE).isoformat(),
        },
    }
