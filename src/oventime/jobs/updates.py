from datetime import timedelta
import logging
import pandas as pd

import oventime.core.diagnostic
import oventime.core.dayahead
import oventime.cache.cache

logger = logging.getLogger(__name__)


def update_cache(times, source_version="v1"):
    oventime.cache.cache.init_db()
    for ts in times:
        diag = oventime.core.diagnostic.output(target_time=ts)
        #dayahead = oventime.core.dayahead.output()
        oventime.cache.cache.save(diag, source_version=source_version)


def update_cache_curr(source_version="v1"):
    oventime.cache.cache.init_db()

    data = oventime.core.diagnostic.data_processing.init_data()
    last_ts = oventime.cache.cache.get_last_ts()

    if last_ts is None:
        # Cache vide : on écrit uniquement le point le plus récent
        times = [data.index.max()]
    else:
        # On backfille tous les points manquants depuis le dernier ts en cache
        times = data.index[data.index > last_ts]

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
    now = pd.Timestamp.utcnow().floor("15min")
    times = pd.date_range(
        now - timedelta(hours=48),
        now - timedelta(hours=1),
        freq="15min"
    )

    update_cache_curr()