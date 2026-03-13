from datetime import timedelta
import pandas as pd

import oventime.core.diagnostic
import oventime.core.dayahead
import oventime.cache.cache


def update_cache(times, source_version="v1"):
    oventime.cache.cache.init_db()
    for ts in times:
        diag = oventime.core.diagnostic.output(target_time=ts)
        #dayahead = oventime.core.dayahead.output()
        oventime.cache.cache.save(diag, source_version=source_version)

def update_cache_curr(source_version="v1"):
    oventime.cache.cache.init_db()

    # Dernier ts en cache
    last = oventime.cache.cache.get_last_ts()  # à ajouter dans cache.py
    now = pd.Timestamp.utcnow().floor("15min")

    if last is None:
        times = [now]
    else:
        times = pd.date_range(last + pd.Timedelta("15min"), now, freq="15min")

    for ts in times:
        diag = oventime.core.diagnostic.output(target_time=ts)
        dayahead = oventime.core.dayahead.output(now=ts)
        if diag["time"] == dayahead["time"]:
            oventime.cache.cache.save(diag | dayahead, source_version=source_version)

if __name__ == "__main__":
    # exemple : recalcul des 48 dernières heures
    now = pd.Timestamp.utcnow().floor("15min")
    times = pd.date_range(
        now - timedelta(hours=48),
        now - timedelta(hours=1),
        freq="15min"
    )

    update_cache_curr()
