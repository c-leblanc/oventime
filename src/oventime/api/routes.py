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



