from datetime import timedelta
import pandas as pd

import oventime.core.diagnostic
import oventime.cache.diagnostic
import oventime.core.dayahead
import oventime.cache.dayahead


def upd_cache_diag(times, source_version="v1"):
    oventime.cache.diagnostic.init_db()
    for ts in times:
        d = oventime.core.diagnostic.output(target_time=ts)
        oventime.cache.diagnostic.save(d, source_version=source_version)

def upd_cache_dayahead(source_version="v1"):
    oventime.cache.dayahead.init_db()
    d = oventime.core.dayahead.output()
    oventime.cache.dayahead.save(d, source_version=source_version)


if __name__ == "__main__":
    # exemple : recalcul des 48 dernières heures
    now = pd.Timestamp.utcnow().floor("15min")
    times = pd.date_range(
        now - timedelta(hours=48),
        now - timedelta(hours=1),
        freq="15min"
    )

    upd_cache_diag(times)
