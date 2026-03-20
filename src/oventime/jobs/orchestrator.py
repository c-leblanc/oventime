import asyncio
import logging

from oventime.input.data_download import (
    update_eco2mix_data,
    update_price_data,
    should_update_eco2mix,
    should_update_prices,
    last_ts_eco2mix, last_ts_prices
)
from oventime.jobs.updates import update_cache_curr
from oventime.jobs.notifier import notifier
from oventime.config import FREQ_UPDATE

logger = logging.getLogger(__name__)

async def orchestrator_loop(freq=FREQ_UPDATE):
    """
    Coroutine qui tourne en boucle infinie et :
    1. met à jour eco2mix si nécessaire
    2. met à jour les prix si nécessaire
    3. met à jour le cache
    """
    last_timestamp_eco2mix = last_ts_eco2mix()
    last_timestamp_prices = last_ts_prices()

    while True:
        # --- A. eco2mix data ---
        if should_update_eco2mix(last_timestamp_eco2mix):
            try:
                last_timestamp_eco2mix = update_eco2mix_data()
            except Exception as e:
                logger.error(f"[eco2mix] Exception inattendue: {e!r}")

        # --- B. Day-Ahead Prices data --
        if should_update_prices(last_timestamp_prices):
            try:
                last_timestamp_prices = update_price_data()
            except Exception as e:
                logger.error(f"[prices] Exception inattendue: {e!r}")

        # --- C. cache diagnostic ---
        try:
            update_cache_curr()
        except Exception as e:
            logger.error(f"[cache] Exception inattendue: {e!r}")

        # --- D. alertes ---
        try:
            await notifier.check_and_notify()
        except Exception as e:
            logger.error(f"[notifier] Exception inattendue: {e!r}")

        # --- Attente avant prochaine itération ---
        await asyncio.sleep(freq * 60)


if __name__ == "__main__":
    asyncio.run(orchestrator_loop())
