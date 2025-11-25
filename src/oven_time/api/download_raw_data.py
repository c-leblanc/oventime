from entsoe import EntsoePandasClient
import pandas as pd
import os
from pathlib import Path

from oven_time.config import COUNTRY_CODE
from oven_time.config import ENTSOE_API_KEY
from oven_time.config import PROJECT_ROOT

def download_raw_data(start, end):
    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)

    load = client.query_load(country_code=COUNTRY_CODE, start=start, end=end)
    generation = client.query_generation(country_code=COUNTRY_CODE, start=start, end=end, psr_type=None, include_eic=False)

    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    load.to_csv(raw_dir / "load.csv")
    generation.to_csv(raw_dir / "generation.csv")

def download_raw_data_INSTANT():
    now = pd.Timestamp.now(tz='Europe/Paris').floor("15min")
    just_before = now - pd.Timedelta(hours=0.25)
    download_raw_data(start=just_before,end=now)

def download_raw_data_12H():
    now = pd.Timestamp.now(tz='Europe/Paris').floor("15min")
    halfday_ago = now - pd.Timedelta(hours=12)
    download_raw_data(start=halfday_ago,end=now)

def download_raw_data_24H():
    now = pd.Timestamp.now(tz='Europe/Paris').floor("15min")
    yesterday = now - pd.Timedelta(hours=24)
    download_raw_data(start=yesterday,end=now)


