import os
from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # racine du repo


# Tokens
load_dotenv()
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Parameters
RETENTION_DAYS = 10 # Data to keep in memory
FREQ_UPDATE = 5 # Frequency at which data is updated
SCORE_THRESHOLD = 100 # Score above which an automated message is sent


COUNTRY_CODE = "FR" # Country code used by entsoe-py

