import requests
from oven_time.config import ENTSOE_API_KEY
from oven_time.config import BASE_URL


def get_generation_mix(start, end, country="FR"):
    params = {
        "securityToken": ENTSOE_API_KEY,
        "documentType": "A75",
        "processType": "A16",
        "in_Domain": f"10YFR-RTE------C",
        "out_Domain": f"10YFR-RTE------C",
        "periodStart": start,
        "periodEnd": end,
    }
    r = requests.get(BASE_URL, params=params)
    r.raise_for_status()
    return r.text
