import requests
from datetime import timedelta
import pandas as pd
import time

from oven_time.config import PROJECT_ROOT, RETENTION_DAYS, FREQ_UPDATE

BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records"

def fetch_raw(start, end, limit=100, vars=None):
    where = f"date_heure:['{start}' TO '{end}']"

    params = {
        "where": where,
        "order_by": "date_heure ASC",
        "limit": limit,
    }

    if vars is not None:
        # s’assurer qu’on a toujours date_heure
        select_cols = ["date_heure"] + list(vars)
        params["select"] = ",".join(select_cols)

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()["results"]


def fetch_df(start=None, end=None, limit=100, vars=None) -> pd.DataFrame:
    if end==None:
        end = pd.Timestamp.now(tz="UTC")
    if start==None:
        start = end - timedelta(days=7)
    rows = fetch_raw(start=start, end=end, limit=limit, vars=vars)

    # aplati la structure JSON et récupère les champs
    df = pd.json_normalize(rows)  # -> colonnes 'fields.date_heure', 'fields.nucleaire', etc.

    # parse la date et met en index
    df = df.set_index("date_heure").sort_index()
    df.index = pd.to_datetime(df.index)

    return df

def update_eco2mix_data(retention_days=7,verbose=True):
    def log(msg):
        """Small helper to control verbosity."""
        if verbose:
            print(msg)
    
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 1. Load existing data (if available)
    # ------------------------------------------------------------
    eco2mix_file = raw_dir / "eco2mix.csv"
    
    if eco2mix_file.exists():
        existing = pd.read_csv(eco2mix_file, index_col=0, parse_dates=True)
        last_timestamp = existing.index.max()
        log(f"Last timestamp in load file: {last_timestamp}")
    else:
        existing = None
        last_timestamp = None
        log("No existing load file found.")

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
    # 3. Download missing data & concatenate
    # ------------------------------------------------------------
    while start < now:

        new_data = fetch_df(start=start, end=now)

        if existing is not None:
            existing = pd.concat([existing, new_data])
        else:
            existing = new_data

        last_timestamp = existing.index.max()
        start = last_timestamp + pd.Timedelta(minutes=15)

    # ------------------------------------------------------------
    # 5. Remove data older than retention_days
    # ------------------------------------------------------------
    limit = now - pd.Timedelta(days=retention_days)
    existing = existing[existing.index >= limit]

    log(f"Removed data older than: {limit}")

    # ------------------------------------------------------------
    # 6. Save final cleaned dataset
    # ------------------------------------------------------------
    existing.to_csv(eco2mix_file)

    log("Update complete.")


def background_updater(retention_days=RETENTION_DAYS, freq=FREQ_UPDATE):
    while True:
        update_eco2mix_data(retention_days=retention_days, verbose=True)
        time.sleep(freq * 60)  # 5 minutes



if __name__ == "__main__":
    df = fetch_df()
    print(df)
