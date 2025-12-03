import os
from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # racine du repo



load_dotenv()

ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
BASE_URL = "https://api.entsoe.eu/api"
COUNTRY_CODE = "FR"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")