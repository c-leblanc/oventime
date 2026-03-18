from datetime import datetime, timezone, timedelta
import logging

import oventime.core.diagnostic
import oventime.core.dayahead
import oventime.cache.cache

from oventime.utils import floor_dt

logger = logging.getLogger(__name__)


def update_cache(times, source_version="v1"):
    oventime.cache.cache.init_db()
    for ts in times:
        diag = oventime.core.diagnostic.output(target_time=ts)
        oventime.cache.cache.save(diag, source_version=source_version)


def update_cache_curr(source_version="v1"):
    oventime.cache.cache.init_db()

    data = oventime.core.diagnostic.data_processing.init_data()
    last_ts = oventime.cache.cache.get_last_ts()

    if last_ts is None:
        # Cache vide : on écrit uniquement le point le plus récent
        times = [data[-1]["date_heure"]]
    else:
        # On backfille tous les points manquants depuis le dernier ts en cache
        times = [row["date_heure"] for row in data if row["date_heure"] > last_ts]

    if len(times) == 0:
        logger.info("Cache déjà à jour, rien à écrire.")
        return

    for ts in times:
        diag = oventime.core.diagnostic.output(target_time=ts)
        dayahead = oventime.core.dayahead.output(now=ts)
        if diag["time"] == dayahead["time"]:
            oventime.cache.cache.save(diag | dayahead, source_version=source_version)
        else:
            raise ValueError(f"Inconsistent timestamps at {ts}.")

    logger.info(f"{len(times)} point(s) écrits en cache.")


if __name__ == "__main__":
    # exemple : recalcul des 48 dernières heures
    now = floor_dt(datetime.now(timezone.utc))
    times = []
    t = now - timedelta(hours=48)
    end = now - timedelta(hours=1)
    while t <= end:
        times.append(t)
        t += timedelta(minutes=15)

    update_cache_curr()
