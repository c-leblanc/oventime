from entsoe import EntsoePandasClient
import pandas as pd
import os

from oven_time.config import COUNTRY_CODE
from oven_time.config import ENTSOE_API_KEY

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]   # src/electricity_co2_advisor/... -> remonte à la racine
RAW_DIR = PACKAGE_ROOT / "data" / "raw"

now = pd.Timestamp.now(tz='Europe/Paris')
yesterday = now - pd.Timedelta(hours=24)
week_ago = now - pd.Timedelta(hours=24*7)


def download_raw_data(start, end):
    client = EntsoePandasClient(api_key=os.getenv("ENTSOE_API_KEY"))

    type_marketagreement_type = 'A01'
    contract_marketagreement_type = "A01"
    process_type = 'A51'

    load = client.query_load(country_code=COUNTRY_CODE, start=start, end=end)
    generation = client.query_generation(country_code=COUNTRY_CODE, start=start, end=end, psr_type=None, include_eic=False)

    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    load.to_csv(raw_dir / "load.csv")
    generation.to_csv(raw_dir / "generation.csv")
    
def download_raw_data_24H():
    download_raw_data(start=yesterday,end=now)

