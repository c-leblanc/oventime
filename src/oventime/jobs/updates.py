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
    diag = oventime.core.diagnostic.output()
    dayahead = oventime.core.dayahead.output(now=diag["time"])
    if diag["time"]==dayahead["time"]:
        output = (diag | dayahead)
    else: 
        raise ValueError("Inconsistent timestamps.")
    oventime.cache.cache.save(output=output, source_version=source_version)


if __name__ == "__main__":
    # exemple : recalcul des 48 dernières heures
    now = pd.Timestamp.utcnow().floor("15min")
    times = pd.date_range(
        now - timedelta(hours=48),
        now - timedelta(hours=1),
        freq="15min"
    )

    update_cache_curr()
