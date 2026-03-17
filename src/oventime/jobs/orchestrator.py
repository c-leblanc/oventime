import asyncio
import logging
from datetime import datetime

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
        logger.info(f"[{datetime.now()}] Début de l'orchestrateur")

        # --- A. eco2mix data ---
        if should_update_eco2mix(last_timestamp_eco2mix):
            try:
                last_timestamp_eco2mix = update_eco2mix_data()
                logger.info(f"[{datetime.now()}] eco2mix mis à jour")
            except Exception as e:
                logger.error(f"[{datetime.now()}] Erreur mise à jour eco2mix: {e!r}")
        else: logger.info(f"[{datetime.now()}] Eco2mix : pas de mise à jour nécessaire.")

        # --- B. Day-Ahead Prices data --
        if should_update_prices(last_timestamp_prices):
            try:
                last_timestamp_prices = update_price_data()
                logger.info(f"[{datetime.now()}] DA Prices mis à jour")
            except Exception as e:
                logger.error(f"[{datetime.now()}] Erreur mise à jour prices: {e!r}")
        else: logger.info(f"[{datetime.now()}] DA Prices: pas de mise à jour nécessaire.")

        # --- C. cache diagnostic ---
        try:
            update_cache_curr()
            logger.info(f"[{datetime.now()}] Cache mis à jour.")
        except Exception as e:
            logger.error(f"[{datetime.now()}] Erreur mise à jour cache: {e!r}")

        # --- D. alertes ---
        try:
            await notifier.check_and_notify()
        except Exception as e:
            logger.error(f"Erreur alertes: {e!r}")

        # --- Attente avant prochaine itération ---
        await asyncio.sleep(freq * 60)


if __name__ == "__main__":
    asyncio.run(orchestrator_loop())
