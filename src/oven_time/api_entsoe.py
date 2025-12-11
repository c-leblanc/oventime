from entsoe import EntsoePandasClient
import pandas as pd
import time

from oven_time.config import COUNTRY_CODE, RETENTION_DAYS, FREQ_UPDATE
from oven_time.config import ENTSOE_API_KEY
from oven_time.config import PROJECT_ROOT


def update_prod_data(retention_days=7, verbose=True):
    """
    Update the local raw ENTSO-E data files (`load.csv` and `generation.csv`).

    Workflow
    --------
    1. Load existing data if present.
    2. Detect the last timestamp already available.
    3. Download only the missing time interval.
    4. Drop observations older than `retention_days`.
    5. Save clean, updated files.

    Parameters
    ----------
    retention_days : int, default 7
        Number of days of data to keep locally. Older data are discarded.

    verbose : bool, default True
        If True → print progress and diagnostic messages.
        If False → run silently.

    Notes
    -----
    - ENTSO-E timestamps are returned timezone-aware. They are converted to UTC.
    - Data are aligned on a 15-minute granularity.
    """

    def log(msg):
        """Small helper to control verbosity."""
        if verbose:
            print(msg)

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load existing data (if available)
    load_file = raw_dir / "load.csv"
    gen_file = raw_dir / "generation.csv"

    if load_file.exists():
        load = pd.read_csv(load_file, index_col=0, parse_dates=True)
        last_timestamp = load.index.max()
        log(f"Last timestamp in load file: {last_timestamp}")
    else:
        load = None
        last_timestamp = None
        log("No existing load file found.")

    if gen_file.exists():
        generation = pd.read_csv(gen_file, index_col=0, header=[0, 1], parse_dates=True)
        last_timestamp_gen = generation.index.max()
        log(f"Last timestamp in generation file: {last_timestamp_gen}")
    else:
        generation = None
        log("No existing generation file found.")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    log(f"Current time considered: {now}")

    if last_timestamp is None:
        # No local data → start from retention_days ago
        start = now - pd.Timedelta(days=retention_days)
    else:
        # Continue from the next 15-minute step
        start = last_timestamp + pd.Timedelta(minutes=15)
        log(f"Attempting to download data starting from: {start}")

    if start >= now:
        log("Data already up to date. Nothing to download.")
        return

    # 3. Download missing data
    try:
        new_load = client.query_load(
            COUNTRY_CODE, start=start, end=now
        )
        new_gen = client.query_generation(
            COUNTRY_CODE, start=start, end=now,
            psr_type=None, include_eic=False
        )

        # Ensure all timestamps are UTC
        new_load.index = new_load.index.tz_convert("UTC")
        new_gen.index = new_gen.index.tz_convert("UTC")

        log(f"Downloaded data from {start} to {now}")

    except Exception:
        log(f"No new data available (last local data = {last_timestamp}).")
        return

    # 4. Concatenate with existing data
    if load is not None:
        load = pd.concat([load, new_load])
        generation = pd.concat([generation, new_gen])
    else:
        load = new_load
        generation = new_gen

    # 5. Remove data older than retention_days
    limit = now - pd.Timedelta(days=retention_days)
    load = load[load.index >= limit]
    generation = generation[generation.index >= limit]

    log(f"Removed data older than: {limit}")

    # 6. Save final cleaned dataset
    load.to_csv(load_file)
    generation.to_csv(gen_file)

    log("Production data update complete.")


def update_price_data(retention_days=7, verbose=True):
    """
    Update the local raw ENTSO-E day-ahead price file (dayahead.csv).

    Logic
    -----
    - Load local data if present.
    - Detect the last timestamp already locally available.
    - Download missing data *from last timestamp+1h up to tomorrow*.
    - Keep only the last `retention_days` days (BUT always include tomorrow).
    - Save updated CSV.

    Notes
    -----
    - ENTSO-E returns timezone-aware timestamps (converted to UTC).
    """

    def log(msg):
        if verbose:
            print(msg)

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    price_file = raw_dir / "dayahead.csv"

    # 1. Load local data
    if price_file.exists():
        prices = pd.read_csv(price_file, index_col=0, parse_dates=True)
        last_ts = prices.index.max()
        log(f"Last timestamp in prices file: {last_ts}")
    else:
        prices = None
        last_ts = None
        log("No existing price file found.")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    tomorrow = (now + pd.Timedelta(days=1)).normalize()  # midnight next day

    if last_ts is None:
        # First download: fetch from retention_days ago
        start = now - pd.Timedelta(days=retention_days)
    else:
        # Continue from next hour
        start = last_ts + pd.Timedelta(hours=1)

    end = tomorrow + pd.Timedelta(days=1)  # full day-ahead horizon
    log(f"Download window: {start} → {end}")

    if start >= end:
        log("Data already up to date. Nothing to download.")
        return

    # 3. Download missing price data
    try:
        new_prices = client.query_day_ahead_prices(
            COUNTRY_CODE,
            start=start,
            end=end
        )
        new_prices.index = new_prices.index.tz_convert("UTC")
        log(f"Downloaded {len(new_prices)} price rows.")
    except Exception as e:
        log(f"No new price data available. ({e})")
        return

    # 4. Concatenate
    if prices is not None:
        prices = pd.concat([prices, new_prices])
        prices = prices[~prices.index.duplicated(keep="last")]
    else:
        prices = new_prices

    # 5. Remove old data (but keep tomorrow)
    limit = now - pd.Timedelta(days=retention_days)
    keep_from = min(limit, tomorrow)  # never drop tomorrow
    prices = prices[prices.index >= keep_from]

    log(f"Removed data older than: {limit}.")

    # 6. Save
    prices.to_csv(price_file, header=False)
    log("Day-ahead price update complete.")

def should_update_prices():
    """Retourne True si :
    - il est passé midi (heure locale)
    - et les prix de demain ne sont pas encore stockés
    """
    price_file = PROJECT_ROOT / "data" / "raw" / "dayahead.csv"
    if not price_file.exists():
        return True  # on doit télécharger au moins une fois

    prices = pd.read_csv(price_file, index_col=0, parse_dates=True)

    now_local = pd.Timestamp.now().tz_localize("Europe/Paris").tz_convert("Europe/Paris")
    if now_local.hour < 12:
        return False  # pas encore l’heure de vérifier

    tomorrow = (now_local + pd.Timedelta(days=1)).normalize()

    # Vérifier si demain est dans les index
    return tomorrow not in prices.index.normalize().unique()


def background_updater(retention_days=RETENTION_DAYS, freq = FREQ_UPDATE):
    while True:
        update_prod_data(retention_days=retention_days, verbose=True)
        time.sleep(freq * 60)  # 5 minutes


if __name__ == "__main__":
    update_price_data()
