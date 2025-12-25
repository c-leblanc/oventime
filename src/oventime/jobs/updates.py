from datetime import timedelta
import pandas as pd

from oventime.core.diagnostic import diagnostic
from oventime.cache.diagnostic import init_db, save_diagnostic


def upd_cache_diag(times, source_version="v1"):
    init_db()
    for ts in times:
        d = diagnostic(target_time=ts)
        save_diagnostic(d, source_version=source_version)

def upd_cache_dayahead()

if __name__ == "__main__":
    # exemple : recalcul des 48 dernières heures
    now = pd.Timestamp.utcnow().floor("15min")
    times = pd.date_range(
        now - timedelta(hours=48),
        now - timedelta(hours=1),
        freq="15min"
    )

    upd_cache_diag(times)
