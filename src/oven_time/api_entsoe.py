from entsoe import EntsoePandasClient
import pandas as pd
import time

from oven_time.config import COUNTRY_CODE, RETENTION_DAYS, FREQ_UPDATE
from oven_time.config import ENTSOE_API_KEY
from oven_time.config import PROJECT_ROOT


def update_raw_data(retention_days=7, verbose=True):
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

    # ------------------------------------------------------------
    # 1. Load existing data (if available)
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # 2. Determine download window
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # 3. Download missing data
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # 4. Concatenate with existing data
    # ------------------------------------------------------------
    if load is not None:
        load = pd.concat([load, new_load])
        generation = pd.concat([generation, new_gen])
    else:
        load = new_load
        generation = new_gen

    # ------------------------------------------------------------
    # 5. Remove data older than retention_days
    # ------------------------------------------------------------
    limit = now - pd.Timedelta(days=retention_days)
    load = load[load.index >= limit]
    generation = generation[generation.index >= limit]

    log(f"Removed data older than: {limit}")

    # ------------------------------------------------------------
    # 6. Save final cleaned dataset
    # ------------------------------------------------------------
    load.to_csv(load_file)
    generation.to_csv(gen_file)

    log("Update complete.")


def background_updater(retention_days=RETENTION_DAYS, freq = FREQ_UPDATE):
    while True:
        update_raw_data(retention_days=retention_days, verbose=True)
        time.sleep(freq * 60)  # 5 minutes


if __name__ == "__main__":
    update_raw_data()
