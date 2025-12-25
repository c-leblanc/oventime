import asyncio
from datetime import datetime
import pandas as pd

from oventime.input.data_download import (
    update_eco2mix_data,
    update_price_data,
    should_update_eco2mix,
    should_update_prices,
    last_ts_eco2mix, last_ts_prices
)
from oventime.jobs.updates import upd_cache_diag, upd_cache_dayahead
from oventime.config import FREQ_UPDATE


async def orchestrator_loop(freq=FREQ_UPDATE):
    """
    Coroutine qui tourne en boucle infinie et :
    1. met à jour eco2mix si nécessaire
    2. met à jour les prix si nécessaire
    3. met à jour le cache diagnostic
    """
    last_timestamp_eco2mix = last_ts_eco2mix()
    last_timestamp_prices = last_ts_prices()

    while True:
        print(f"[{datetime.now()}] Début de l'orchestrateur")

        # 1. Live data and diagnostic
        # --- A. eco2mix data ---
        if should_update_eco2mix(last_timestamp_eco2mix):
            try:
                last_timestamp_eco2mix = update_eco2mix_data(verbose=True)
                print(f"[{datetime.now()}] eco2mix mis à jour")
            except Exception as e:
                print(f"[{datetime.now()}] Erreur mise à jour eco2mix: {e!r}")
        else: print(f"[{datetime.now()}] Eco2mix : pas de mise à jour nécessaire.")

        # --- B. cache diagnostic ---
        print(last_timestamp_eco2mix - pd.Timedelta(hours=2))
        times = pd.date_range(
            start = last_timestamp_eco2mix - pd.Timedelta(hours=2),
            end = last_timestamp_eco2mix,
            freq="15min"
        )
        print(times)
        try:
            upd_cache_diag(times)
            print(f"[{datetime.now()}] Cache diagnostic mis à jour, ajout(s): {times}")
        except Exception as e:
            print(f"[{datetime.now()}] Erreur mise à jour cache diagnostic: {e!r}")


        # 2. Day-Ahead
        # --- A. Day-Ahead Prices data --
        if should_update_prices(last_timestamp_prices):
            try:
                last_timestamp_prices = update_price_data(verbose=True)
                print(f"[{datetime.now()}] DA Prices mis à jour")
            except Exception as e:
                print(f"[{datetime.now()}] Erreur mise à jour prices: {e!r}")
        else: print(f"[{datetime.now()}] DA Prices: pas de mise à jour nécessaire.")
        # --- B. cache dayahead ---
        try:
            upd_cache_dayahead()
            print(f"[{datetime.now()}] Cache diagnostic mis à jour.")
        except Exception as e:
            print(f"[{datetime.now()}] Erreur mise à jour cache dayahead: {e!r}")


        # --- Attente avant prochaine itération ---
        await asyncio.sleep(freq * 60)


if __name__ == "__main__":
    asyncio.run(orchestrator_loop())
