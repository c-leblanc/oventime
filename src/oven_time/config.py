import os
from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # racine du repo

############################################
# Tokens
############################################

load_dotenv(PROJECT_ROOT / ".env")
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
COUNTRY_CODE = "FR" # Country code used by entsoe-py

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Verify required tokens are present
_missing = [
    name for name, val in (
        ("ENTSOE_API_KEY", ENTSOE_API_KEY),
        ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
    ) if not val
]
if _missing:
    raise RuntimeError(
        f"Missing required environment variable(s): {', '.join(_missing)}. "
        f"Please set them in {str(PROJECT_ROOT / '.env')} or in your environment."
    )

############################################
# Parameters
############################################

## Time Zone
TIMEZONE = "Europe/Paris"

## Data
RETENTION_DAYS = 22 # Data to keep in memory
FREQ_UPDATE_ECO2MIX = 20 # Eco2Mix Data : Time elapsed since last data that triggers an update attempt (in minutes).
MIN_FORESIGHT_PRICES = 12 # Price Data from ENTSO-E : Update attempt triggered if last data less than MIN_FORESIGHT_PRICES in the future

## Automatic Updates
HIGH_SCORE_THRESHOLD = 100 # Score above which an automated "abundance" message is sent
LOW_SCORE_THRESHOLD = 10 # Score below which an automated "tension" message is sent

## Best window determination
WINDOW_METHOD = "otsu"
OTSU_SEVERITY = 1
WINDOW_RANGE = 24

