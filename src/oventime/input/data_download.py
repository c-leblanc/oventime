import requests
import logging
from datetime import timedelta
import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

from oventime.config import DATA_DIR, RETENTION_DAYS, FREQ_UPDATE_ECO2MIX, MIN_FORESIGHT_PRICES, COUNTRY_CODE, ENTSOE_API_KEY
from oventime.utils import trim_trailing_nans

logger = logging.getLogger(__name__)

ECO2MIX_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records"

COLS_TRIM = [
    "eolien", "solaire", "hydraulique_fil_eau_eclusee",  # → RENEWABLE
    "nucleaire",                                           # → NUCLEAR
    "hydraulique_lacs", "hydraulique_step_turbinage",     # → STORAGE
    "pompage", "destockage_batterie", "stockage_batterie",# → STORAGE
    "gaz_ccg",                                            # → GAS_CCG
    "gaz_tac",                                            # → GAS_TAC
    "charbon", "gaz_autres", "fioul_tac", "fioul_autres", # → OTHER
    "gaz_cogen", "fioul_cogen", "bioenergies",            # → OTHER
]

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
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

def update_eco2mix_data(
        retention_days: int = RETENTION_DAYS
        ) -> pd.Timestamp:
    """
    Update local eco2mix data from API requests up to now, cleans up data older than <retention_days> days ago.
    
    :param retention_days: Period for which data is kept locally (changes prefered in oven_time.config -> RETENTION_DAYS)
    :type retention_days: int
    :return: Last timestamp without missing data after the update
    :rtype: Timestamp
    """
    
    logger.info("\n[Eco2Mix Data Update]")
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load existing data
    eco2mix_file = raw_dir / "eco2mix.parquet"
    if eco2mix_file.exists():
        local = pd.read_parquet(eco2mix_file)
        local = trim_trailing_nans(local, cols = COLS_TRIM)
        if len(local) == 0:
            last_timestamp = None
            logger.info("Local data - None left after trimming")
        else:
            last_timestamp = local.index.max()
            logger.info(f"Local data - Last timestamp: {last_timestamp}")
    else:
        local = None
        last_timestamp = None
        logger.info("Local data - None")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    if last_timestamp is None:
        start = now - pd.Timedelta(days=retention_days)
    else:
        start = last_timestamp + pd.Timedelta(minutes=15)
    
    if start >= now:
        logger.info("Data already up to date. Nothing to download.")
        return(last_timestamp)
    else: logger.info(f"Attempting to download data starting from: {start}")

    # 3. Download missing data & concatenate
    combined = None
    while start < now:
        try:
            new_data = eco2mix_df(start=start, end=now)
        except Exception as e:
            logger.error(f"Error fetching eco2mix_df(start={start}, end={now}) : {e!r}")
            break

        if new_data is None or len(new_data) == 0:
            logger.info(f"No data for {start} -> {now}, stop downloading.")
            break

        if not isinstance(new_data.index, pd.DatetimeIndex):
            logger.error(f"Index error: not interpretable as date-time.")
            break
        
        new_data.index = pd.to_datetime(new_data.index, utc=True)
        logger.info(f"Downloaded data from {new_data.index.min()} to {new_data.index.max()}")
        
        if local is not None:
            if new_data.isna().values.all():
                logger.error("Downloaded data is empty.")
                break
            else: combined = pd.concat([local, new_data])
        else:
            combined = new_data

        local = combined
        last_timestamp = combined.index.max()
        start = last_timestamp + pd.Timedelta(minutes=15)

    if combined is None or len(combined) == 0:
        logger.error("No eco2mix data available.")
        return

    # 4. Remove data older than retention_days
    limit = now - pd.Timedelta(days=retention_days)
    if min(combined.index) < limit:
        combined = combined[combined.index >= limit]
        logger.info(f"Removed data older than: {limit}")

    # 5. Save final cleaned dataset
    combined.to_parquet(eco2mix_file)
    logger.info("Update completed.")

    # 6. Return the last timestamp with complete data
    combined = trim_trailing_nans(combined, cols=COLS_TRIM)
    last_timestamp = combined.index.max()
    return(last_timestamp)

def update_price_data(
        retention_days: int = RETENTION_DAYS
        ) -> pd.Timestamp:
    """
    Update local price data from the ENTSO-E API up to now, cleans up data older than <retention_days> days ago.
    
    :param retention_days: Period for which data is kept locally (changes prefered in oven_time.config -> RETENTION_DAYS)
    :type retention_days: int
    :return: Last timestamp without missing data after the update
    :rtype: Timestamp
    """

    logger.info("\n[Day-Ahead Price Data Update]")

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    price_file = raw_dir / "DAprices.parquet"

    # 1. Load local data as a Series (file may have no header)
    if price_file.exists():
        local = pd.read_parquet(price_file)
        # ensure index is timezone-aware UTC
        local.index = pd.to_datetime(local.index, utc=True)
        last_timestamp = local.index.max()
        logger.info(f"Local data - Last timestamp: {last_timestamp}")
    else:
        local = None
        last_timestamp = None
        logger.info("No existing price file found.")

    # 2. Determine download window
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    if last_timestamp is None:
        start = now - pd.Timedelta(days=retention_days)
    else:
        start = last_timestamp + pd.Timedelta(minutes=15)
    end = now + pd.Timedelta(days=2) # overshoot to include the next day entirely
    logger.info(f"Attempting to download from {start} to {end}")

    # 3. Download missing price data
    try:
        new_data = client.query_day_ahead_prices(COUNTRY_CODE, start=start, end=end)
    except NoMatchingDataError: 
        logger.info(f"Data already up to date. Nothing to download.")
        return(last_timestamp)
    except Exception as e:
        logger.error(f"Error when fetching price data: {e!r}")
        return(last_timestamp)

    new_data = new_data.to_frame(name="price")

    # Some clients return tz-naive timestamps — ensure UTC tz
    if new_data.index.tz is None: new_data.index = new_data.index.tz_localize("UTC")
    else: new_data.index = new_data.index.tz_convert("UTC")

    logger.info(f"Downloaded data from {new_data.index.min()} to {new_data.index.max()}")

    # 4. Concatenate   
    if local is not None:
        combined = pd.concat([local, new_data])
    else:
        combined = new_data

    # remove duplicates keeping the last (new data should override)
    combined = combined[~combined.index.duplicated(keep="last")]

    # sort index ascending (useful after concat)
    combined = combined.sort_index()

    # 5. Remove old data but always keep tomorrow
    limit = now - pd.Timedelta(days=retention_days)
    if min(combined.index) < limit:
        combined = combined[combined.index >= limit]
        logger.info(f"Removed data older than: {limit}.")

    # 6. Save in a parquet file
    combined.to_parquet(price_file)
    logger.info("Update completed.")

    # 7. Return the last timestamp with complete data
    combined = trim_trailing_nans(combined)
    last_timestamp = combined.index.max()
    return(last_timestamp)

def last_ts_prices():
    price_file = DATA_DIR / "raw" / "DAprices.parquet"
    if not price_file.exists():
        return pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=RETENTION_DAYS)
    prices = pd.read_parquet(price_file)
    if len(prices) == 0:
        return pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=RETENTION_DAYS)
    return pd.to_datetime(prices.index[-1], utc=True)

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
        last_timestamp = last_ts_prices()

    now = pd.Timestamp.now(tz="UTC")
    return last_timestamp < (now + pd.Timedelta(hours=min_foresight_prices))

def last_ts_eco2mix():
    eco2mix_file = DATA_DIR / "raw" / "eco2mix.parquet"
    # Check if the eco2mix file exists
    if not eco2mix_file.exists():
        return pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=RETENTION_DAYS)
    # Load and remove final rows with missing data
    eco2mix = pd.read_parquet(eco2mix_file)
    eco2mix = trim_trailing_nans(eco2mix, cols=COLS_TRIM)
    # Return last timestamp (or default if no rows left) 
    if len(eco2mix) == 0:
        return pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=RETENTION_DAYS)
    return pd.to_datetime(eco2mix.index, utc=True).max()

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
        last_timestamp = last_ts_eco2mix()
    now = pd.Timestamp.now(tz="UTC")
    return last_timestamp < (now - pd.Timedelta(minutes=freq_update_eco2mix))

