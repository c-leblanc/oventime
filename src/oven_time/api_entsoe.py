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
    def log(msg):
        if verbose:
            print(msg)

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    price_file = raw_dir / "dayahead.csv"

    # 1. Load local data as a Series (file may have no header)
    if price_file.exists():
        # header=None ensures we read files without header correctly
        df_local = pd.read_csv(price_file, header=None, index_col=0, parse_dates=True)
        # convert to Series (first data column)
        local = df_local.iloc[:, 0].copy()
        # remove any column/name metadata
        local.name = None
        # ensure index is timezone-aware UTC
        if local.index.tz is None:
            local.index = local.index.tz_localize("UTC")
        last_ts = local.index.max()
        log(f"Last timestamp in prices file: {last_ts}")
    else:
        local = None
        last_ts = None
        log("No existing price file found.")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    tomorrow = (now + pd.Timedelta(days=1)).normalize()  # midnight next day

    if last_ts is None:
        start = now - pd.Timedelta(days=retention_days)
    else:
        # make sure last_ts is tz-aware UTC
        if last_ts.tz is None:
            last_ts = last_ts.tz_localize("UTC")
        start = last_ts + pd.Timedelta(hours=1)

    # we want to include next day entirely (end exclusive okay)
    end = tomorrow + pd.Timedelta(days=1)
    log(f"Download window: {start} → {end}")

    if start >= end:
        log("Data already up to date. Nothing to download.")
        return

    # 3. Download missing price data
    try:
        new_prices = client.query_day_ahead_prices(COUNTRY_CODE, start=start, end=end)
    except Exception as e:
        log(f"No new price data available. ({e})")
        return

    # normalize new_prices to Series without name and tz-aware index
    if isinstance(new_prices, pd.DataFrame):
        new = new_prices.iloc[:, 0].copy()
    else:
        new = new_prices.copy()

    new.name = None
    # Some clients return tz-naive timestamps — ensure UTC tz
    if new.index.tz is None:
        # if timestamps look like they are UTC, localize; otherwise adjust accordingly
        new.index = new.index.tz_localize("UTC")
    else:
        new.index = new.index.tz_convert("UTC")

    log(f"Downloaded {len(new)} price rows.")

    # 4. Concatenate Series safely
    if local is not None:
        combined = pd.concat([local, new])
    else:
        combined = new

    # remove duplicates keeping the last (new data should override)
    combined = combined[~combined.index.duplicated(keep="last")]

    # sort index ascending (useful after concat)
    combined = combined.sort_index()

    # 5. Remove old data but always keep tomorrow
    limit = now - pd.Timedelta(days=retention_days)
    # keep_from should be the smaller (earlier) of limit and tomorrow so we never drop tomorrow
    keep_from = min(limit, tomorrow)
    combined = combined[combined.index >= keep_from]

    log(f"Removed data older than: {limit}.")

    # 6. Save as CSV without header (you wanted no header / no column name)
    # write index + values, no header row
    combined.to_csv(price_file, header=False)
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
