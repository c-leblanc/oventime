from datetime import datetime, timezone, timedelta
import logging

import oventime.core.diagnostic
import oventime.core.dayahead
import oventime.cache.cache

from oventime.utils import floor_dt, to_epoch

logger = logging.getLogger(__name__)


def compute_and_store(ts, source_version="v1"):
    try:
        diag = oventime.core.diagnostic.output(target_time=ts)
    except (ValueError, IndexError) as e:
        logger.info(f"Skip {ts} (diagnostic): {e}")
        return False

    # dayahead (nextwind) : on essaie, mais c'est pas bloquant
    try:
        dayahead = oventime.core.dayahead.output(now=ts)
        if diag["time"] == dayahead["time"]:
            diag.update(dayahead)
    except (ValueError, IndexError):
        pass  # pas de prix futurs pour ce ts, c'est normal pour l'historique

    oventime.cache.cache.save(diag, source_version=source_version)
    return True
    
def update_timeline(latest_ts):
    last_tl_ts = oventime.cache.cache.get_last_ts_timeline()

    if last_tl_ts is not None and last_tl_ts >= latest_ts:
        logger.info("Timeline déjà à jour.")
        return

    tl = oventime.core.dayahead.timeline_output(now=latest_ts)

    if not tl:
        return

    oventime.cache.cache.save_timeline(
        to_epoch(latest_ts),
        tl["slots"],
        threshold_go=tl["threshold_go"],
        threshold_or=tl["threshold_or"]
    )

    logger.info("Timeline mise à jour.")


def update_cache_curr(source_version="v1"):
    oventime.cache.cache.init_db()

    data = oventime.core.diagnostic.data_processing.init_data()

    now = data[-1]["date_heure"]
    cutoff = now - timedelta(hours=48)

    target_times = [
        row["date_heure"]
        for row in data
        if cutoff <= row["date_heure"] <= now
    ]

    existing_ts = oventime.cache.cache.get_ts_in_range(cutoff, now)

    missing_times = [ts for ts in target_times if ts not in existing_ts]

    if not missing_times:
        logger.info("Cache déjà complet sur les 48 dernières heures.")
    else:
        logger.info(f"{len(missing_times)} point(s) à calculer.")

        for ts in missing_times:
            compute_and_store(ts, source_version)

    update_timeline(now)