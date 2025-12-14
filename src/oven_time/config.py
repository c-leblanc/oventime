import os
from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # racine du repo

############################################
# Tokens
############################################

load_dotenv()
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
COUNTRY_CODE = "FR" # Country code used by entsoe-py

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


############################################
# Parameters
############################################

## Data
RETENTION_DAYS = 10 # Data to keep in memory
FREQ_UPDATE = 5 # Frequency at which data is updated

## Automatic Updates
HIGH_SCORE_THRESHOLD = 100 # Score above which an automated "abundance" message is sent
LOW_SCORE_THRESHOLD = 0 # Score above which an automated "tension" message is sent

## Best window determination
WINDOW_METHOD = "otsu"
OTSU_SEVERITY = 0.5

