import os
from dotenv import load_dotenv

load_dotenv()

ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
BASE_URL = "https://api.entsoe.eu/api"

COUNTRY_CODE = "FR"
