import requests
from datetime import timedelta
import pandas as pd
from entsoe import EntsoePandasClient

from oven_time.config import PROJECT_ROOT, RETENTION_DAYS, FREQ_UPDATE_ECO2MIX, MIN_FORESIGHT_PRICES, COUNTRY_CODE, ENTSOE_API_KEY

ECO2MIX_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records"




def eco2mix_raw(start, end, limit=100, vars=None):
    where = f"date_heure:['{start}' TO '{end}']"

    params = {
        "where": where,
        "order_by": "date_heure ASC",
        "limit": limit,
    }

    if vars is not None:
        select_cols = ["date_heure"] + list(vars)
        params["select"] = ",".join(select_cols)

    resp = requests.get(ECO2MIX_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()["results"]

def eco2mix_df(start=None, end=None, limit=100, vars=None) -> pd.DataFrame:
    if end is None:
        end = pd.Timestamp.now(tz="UTC")
    if start is None:
        start = end - timedelta(days=RETENTION_DAYS)

    rows = eco2mix_raw(start=start, end=end, limit=limit, vars=vars)

    if not rows:
        return pd.DataFrame().set_index(
            pd.DatetimeIndex([], name="date_heure")
        )

    df = pd.json_normalize(rows)

    if "date_heure" not in df.columns:
        if "fields.date_heure" in df.columns:
            df["date_heure"] = df["fields.date_heure"]
        else:
            return pd.DataFrame().set_index(
                pd.DatetimeIndex([], name="date_heure")
            )

    df["date_heure"] = pd.to_datetime(df["date_heure"], errors="coerce", utc=True)
    df = df.dropna(subset=["date_heure"])

    if df.empty:
        return pd.DataFrame().set_index(
            pd.DatetimeIndex([], name="date_heure")
        )

    df = df.set_index("date_heure").sort_index()

    return df

def update_eco2mix_data(
        retention_days: int = RETENTION_DAYS, 
        verbose: bool = True
        ) -> pd.Timestamp:
    """
    Update local eco2mix data from API requests up to now, cleans up data older than <retention_days> days ago.
    
    :param retention_days: Period for which data is kept locally (changes prefered in oven_time.config -> RETENTION_DAYS)
    :type retention_days: int
    :param verbose: Logging
    :type verbose: bool
    :return: Last timestamp without missing data after the update
    :rtype: Timestamp
    """
    def log(msg):
        if verbose:
            print(msg)
    
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load existing data
    eco2mix_file = raw_dir / "eco2mix.csv"
    if eco2mix_file.exists():
        local = pd.read_csv(eco2mix_file, index_col=0, parse_dates=True)
        while len(local) > 0 and local.iloc[-1].isna().any():
            local = local.iloc[:-1]
        if len(local) == 0:
            last_timestamp = None
            log("Existing data - None left after trimming")
        else:
            last_timestamp = local.index.max()
            log(f"Existing data - Last timestamp: {last_timestamp}")
    else:
        local = None
        last_timestamp = None
        log("Existing data - None")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    if last_timestamp is None:
        start = now - pd.Timedelta(days=retention_days)
    else:
        start = last_timestamp + pd.Timedelta(minutes=15)
    log(f"Attempting to download data starting from: {start}")

    if start >= now:
        log("Data already up to date. Nothing to download.")
        return(last_timestamp)

    # 3. Download missing data & concatenate
    combined = None
    while start < now:
        try:
            new_data = eco2mix_df(start=start, end=now)
        except Exception as e:
            log(f"[update_eco2mix_data] Error fetching eco2mix_df(start={start}, end={now}) : {e!r}")
            break

        if new_data is None or len(new_data) == 0:
            log(f"[update_eco2mix_data] No data for {start} -> {now}, stop downloading.")
            break

        if not isinstance(new_data.index, pd.DatetimeIndex):
            log(f"[update_eco2mix_data] Index error: not interpretable as date-time.")
            break

        log(f"Downloaded data from {new_data.index.min()} to {new_data.index.max()}")
        new_data.index = pd.to_datetime(new_data.index, utc=True)

        if local is not None:
            combined = pd.concat([local, new_data])
        else:
            combined = new_data

        local = combined
        last_timestamp = combined.index.max()
        start = last_timestamp + pd.Timedelta(minutes=15)

    if combined is None or len(combined) == 0:
        log("No eco2mix data available.")
        return

    # 5. Remove data older than retention_days
    limit = now - pd.Timedelta(days=retention_days)
    combined = combined[combined.index >= limit]
    log(f"Removed data older than: {limit}")

    # 6. Save final cleaned dataset
    combined.to_csv(eco2mix_file)
    log("Update complete.")

    # 7. Return the last timestamp with complete data
    while len(combined) > 0 and combined.iloc[-1].isna().any():
            combined = combined.iloc[:-1]
    last_timestamp = combined.index.max()
    return(last_timestamp)

def update_price_data(
        retention_days: int = RETENTION_DAYS, 
        verbose: bool = True
        ) -> pd.Timestamp:
    """
    Update local price data from the ENTSO-E API up to now, cleans up data older than <retention_days> days ago.
    
    :param retention_days: Period for which data is kept locally (changes prefered in oven_time.config -> RETENTION_DAYS)
    :type retention_days: int
    :param verbose: Logging
    :type verbose: bool
    :return: Last timestamp without missing data after the update
    :rtype: Timestamp
    """
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
        # ensure index is timezone-aware UTC
        local.index = pd.to_datetime(local.index, utc=True)
        last_timestamp = local.index.max()
        log(f"Last timestamp in prices file: {last_timestamp}")
    else:
        local = None
        last_timestamp = None
        log("No existing price file found.")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")

    if last_timestamp is None:
        start = now - pd.Timedelta(days=retention_days)
    else:
        start = last_timestamp + pd.Timedelta(minutes=15)

    # overshoot to include the next day entirely
    end = now + pd.Timedelta(days=2)
    log(f"Download window: {start} → {end}")


    # 3. Download missing price data
    try:
        new_data = client.query_day_ahead_prices(COUNTRY_CODE, start=start, end=end)
    except Exception as e:
        log(f"No new price data available. ({e})")
        return(last_timestamp)

    # normalize new_prices to Series without name and tz-aware index
    if isinstance(new_data, pd.DataFrame):
        new_data = new_data.iloc[:, 0]

    # Some clients return tz-naive timestamps — ensure UTC tz
    if new_data.index.tz is None: new_data.index = new_data.index.tz_localize("UTC")
    else: new_data.index = new_data.index.tz_convert("UTC")

    log(f"Downloaded data from {new_data.index.min()} to {new_data.index.max()}")

    # 4. Concatenate Series safely
    new_data.name = None # Avoids problem with concatenation    
    if local is not None:
        local.name = None
        combined = pd.concat([local, new_data])
    else:
        combined = new_data

    # remove duplicates keeping the last (new data should override)
    combined = combined[~combined.index.duplicated(keep="last")]

    # sort index ascending (useful after concat)
    combined = combined.sort_index()

    # 5. Remove old data but always keep tomorrow
    limit = now - pd.Timedelta(days=retention_days)
    combined = combined[combined.index >= limit]
    log(f"Removed data older than: {limit}.")

    # 6. Save as CSV without header (you wanted no header / no column name)
    # write index + values, no header row
    combined.to_csv(price_file, header=False)
    log("Day-ahead price update complete.")

    # 7. Return the last timestamp with complete data
    while len(combined) > 0 and pd.isna(combined.iloc[-1]):
            combined = combined.iloc[:-1]
    last_timestamp = combined.index.max()
    return(last_timestamp)

def should_update_prices(
        last_timestamp: pd.Timestamp = None,
        min_foresight_prices: int = MIN_FORESIGHT_PRICES
        )-> bool:
    """
    Determines if a request to the ENTSO-E API to update prices is worth trying, i.e. if there is a chance that new data is available.
    
    :param last_timestamp: Last timestamp present (and complete) in the data. Returned by update_price_data().
    :type last_timestamp: pd.Timestamp
    :param min_forward_prices: Minimum expected foresight (in hours) for price data before trigerring an update attempt. (changes prefered in oven_time.config -> MIN_FORESIGHT_PRICES)
    :type min_forward_prices: int
    :return: True if an update is worth trying.
    :rtype: bool
    """
    if last_timestamp is None:
        price_file = PROJECT_ROOT / "data" / "raw" / "dayahead.csv"
        if not price_file.exists():
            return True
        prices = pd.read_csv(price_file, index_col=0, parse_dates=True)
        if len(prices) == 0:
            return True
        last_timestamp = pd.to_datetime(prices.index, utc=True).max()

    now = pd.Timestamp.now(tz="UTC")
    return last_timestamp < (now + pd.Timedelta(minutes=min_foresight_prices))


def should_update_eco2mix(
        last_timestamp: pd.Timestamp = None,
        freq_update_eco2mix: int = FREQ_UPDATE_ECO2MIX
        )-> bool:
    """
    Determines if a request to the eco2mix API is worth trying, i.e. if there is a chance that new data is available.
    
    :param last_timestamp: Last timestamp present (and complete) in the data. Returned by update_eco2mix_data().
    :type last_timestamp: pd.Timestamp
    :param freq_update_eco2mix: Time elapsed since last data that triggers an update attempt (in minutes). (changes prefered in oven_time.config -> FREQ_UPDATE_ECO2MIX)
    :type freq_update_eco2mix: int
    :return: True if an update is worth trying.
    :rtype: bool
    """
    if last_timestamp is None:
        eco2mix_file = PROJECT_ROOT / "data" / "raw" / "eco2mix.csv"
        if not eco2mix_file.exists():
            return True
        eco2mix = pd.read_csv(eco2mix_file, index_col=0, parse_dates=True)
        if len(eco2mix) == 0:
            return True
        last_timestamp = pd.to_datetime(eco2mix.index, utc=True).max()
    now = pd.Timestamp.now(tz="UTC")
    return last_timestamp < (now - pd.Timedelta(minutes=freq_update_eco2mix))



if __name__ == "__main__":
    print(update_eco2mix_data())
    print(update_price_data())
