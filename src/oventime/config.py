import os
from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # racine du repo

API_BASE_URL = os.getenv("API_BASE_URL")

############################################
# Tokens
############################################

load_dotenv(PROJECT_ROOT / ".env")
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
COUNTRY_CODE = "FR" # Country code used by entsoe-py

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


############################################
# Parameters
############################################

## Time Zone
TIMEZONE = "Europe/Paris"

## Data
RETENTION_DAYS = 22 # Data to keep in memory
FREQ_UPDATE = 5 # Frequency at which the updating background job runs
FREQ_UPDATE_ECO2MIX = 20 # Eco2Mix Data : Time elapsed since last data that triggers an update attempt (in minutes).
MIN_FORESIGHT_PRICES = 12 # Price Data from ENTSO-E : Update attempt triggered if last data less than MIN_FORESIGHT_PRICES in the future

## Thresholds
LEAF_THRESHOLD = 100 # Score above which an automated "abundance" message is sent
GREEN_ORANGE_THRESHOLD = 70
ORANGE_RED_THRESHOLD = 30
FIRE_THRESHOLD = 10 # Score below which an automated "tension" message is sent

## Best window determination
WINDOW_METHOD = "otsu"
OTSU_SEVERITY = 1
WINDOW_RANGE = 24

