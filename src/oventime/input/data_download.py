import httpx
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

from oventime.config import RETENTION_DAYS, FREQ_UPDATE_ECO2MIX, MIN_FORESIGHT_PRICES, COUNTRY_CODE, ENTSOE_API_KEY
from oventime.utils import trim_trailing_nans, floor_dt
from oventime.input import data_storage

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

ENTSOE_API_URL = "https://web-api.tp.entsoe.eu/api"
# Mapping of country codes to ENTSO-E area EIC codes
COUNTRY_EIC = {
    "FR": "10YFR-RTE------C",
}


def eco2mix_raw(start, end, limit=100, vars_keep=None):
    start_str = start.isoformat() if isinstance(start, datetime) else str(start)
    end_str = end.isoformat() if isinstance(end, datetime) else str(end)
    where = f"date_heure:['{start_str}' TO '{end_str}']"

    params = {
        "where": where,
        "order_by": "date_heure ASC",
        "limit": limit,
    }

    if vars_keep is not None:
        select_cols = ["date_heure"] + list(vars_keep)
        params["select"] = ",".join(select_cols)

    resp = httpx.get(ECO2MIX_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()["results"]


def eco2mix_rows(start=None, end=None, limit=100, vars_keep=None) -> list[dict]:
    if end is None:
        end = datetime.now(timezone.utc)
    if start is None:
        start = end - timedelta(days=RETENTION_DAYS)

    raw = eco2mix_raw(start=start, end=end, limit=limit, vars_keep=vars_keep)

    if not raw:
        return []

    rows = []
    for record in raw:
        # Parse date_heure
        dh = record.get("date_heure") or record.get("fields.date_heure") or record.get("fields", {}).get("date_heure")
        if not dh:
            continue
        try:
            dt = datetime.fromisoformat(dh).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue

        row = {"date_heure": dt}
        for key, value in record.items():
            if key == "date_heure":
                continue
            try:
                row[key] = float(value) if value is not None else None
            except (ValueError, TypeError):
                row[key] = value  # keep non-numeric as-is
        rows.append(row)

    rows.sort(key=lambda r: r["date_heure"])
    return rows


def update_eco2mix_data(
        retention_days: int = RETENTION_DAYS
        ) -> datetime | None:
    """
    Update local eco2mix data from API requests up to now, cleans up data older than <retention_days> days ago.
    """
    logger.info("\n[Eco2Mix Data Update]")
    data_storage.init_raw_db()

    # 1. Load existing data
    local = data_storage.read_eco2mix()
    local = trim_trailing_nans(local, cols=COLS_TRIM)

    if not local:
        last_timestamp = None
        logger.info("Local data - None")
    else:
        last_timestamp = local[-1]["date_heure"]
        logger.info(f"Local data - Last timestamp: {last_timestamp}")

    # 2. Determine download window
    now = floor_dt(datetime.now(timezone.utc))
    earliest_needed = now - timedelta(days=retention_days)

    if last_timestamp is None:
        start = earliest_needed
    else:
        # Si les données locales ne remontent pas assez loin, retélécharger l'historique manquant
        oldest_local = local[0]["date_heure"] if local else None
        if oldest_local is None or oldest_local > earliest_needed + timedelta(hours=1):
            start = earliest_needed
            logger.info(f"Données locales trop récentes ({oldest_local}), retéléchargement depuis {start}")
        else:
            start = last_timestamp + timedelta(minutes=15)

    if start >= now:
        logger.info("Data already up to date. Nothing to download.")
        return last_timestamp
    else:
        logger.info(f"Attempting to download data starting from: {start}")

    # 3. Download missing data
    all_new = []
    while start < now:
        try:
            new_data = eco2mix_rows(start=start, end=now)
        except Exception as e:
            logger.error(f"Error fetching eco2mix data(start={start}, end={now}) : {e!r}")
            break

        if not new_data:
            logger.info(f"No data for {start} -> {now}, stop downloading.")
            break

        logger.info(f"Downloaded data from {new_data[0]['date_heure']} to {new_data[-1]['date_heure']}")
        all_new.extend(new_data)
        last_timestamp = new_data[-1]["date_heure"]
        start = last_timestamp + timedelta(minutes=15)

    if not all_new:
        if not local:
            logger.error("No eco2mix data available.")
            return None
        # Nothing new but local exists
        return last_timestamp

    # 4. Upsert new data (SQLite handles dedup via PRIMARY KEY)
    data_storage.upsert_eco2mix(all_new)

    # 5. Remove data older than retention_days
    limit = now - timedelta(days=retention_days)
    data_storage.delete_eco2mix_before(limit)
    logger.info("Update completed.")

    # 6. Return the last timestamp with complete data
    all_data = data_storage.read_eco2mix()
    all_data = trim_trailing_nans(all_data, cols=COLS_TRIM)
    if not all_data:
        return None
    return all_data[-1]["date_heure"]


# ── ENTSO-E direct API ──────────────────────────────────

def _parse_entsoe_prices(xml_text: str) -> list[dict]:
    """Parse ENTSO-E day-ahead price XML response into list of dicts."""
    root = ET.fromstring(xml_text)
    # Extract namespace from root tag
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    rows = []
    for ts in root.iter(f"{ns}TimeSeries"):
        for period in ts.iter(f"{ns}Period"):
            # Get period start
            start_el = period.find(f".//{ns}start")
            resolution_el = period.find(f"{ns}resolution")
            if start_el is None or start_el.text is None:
                continue

            period_start = datetime.fromisoformat(start_el.text.replace("Z", "+00:00"))

            # Determine resolution (PT15M or PT60M typically)
            resolution_minutes = 60  # default
            if resolution_el is not None and resolution_el.text:
                res_text = resolution_el.text
                if "15M" in res_text:
                    resolution_minutes = 15
                elif "30M" in res_text:
                    resolution_minutes = 30
                elif "60M" in res_text or "1H" in res_text:
                    resolution_minutes = 60

            for point in period.iter(f"{ns}Point"):
                pos_el = point.find(f"{ns}position")
                price_el = point.find(f"{ns}price.amount")
                if pos_el is None or price_el is None:
                    continue
                position = int(pos_el.text) - 1  # 1-based → 0-based
                price = float(price_el.text)
                dt = period_start + timedelta(minutes=resolution_minutes * position)
                rows.append({"date_heure": dt.astimezone(timezone.utc), "price": price})

    rows.sort(key=lambda r: r["date_heure"])
    rows = _interpolate_gaps(rows)
    return rows


def _interpolate_gaps(rows: list[dict]) -> list[dict]:
    """Fill missing 15-min slots by forward-filling the previous price."""
    if len(rows) < 2:
        return rows

    result = [rows[0]]
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        curr = rows[i]
        gap_min = (curr["date_heure"] - prev["date_heure"]).total_seconds() / 60
        steps = int(gap_min // 15)

        if steps > 1:
            for s in range(1, steps):
                result.append({
                    "date_heure": prev["date_heure"] + timedelta(minutes=15 * s),
                    "price": prev["price"],
                })

        result.append(curr)
    return result


def update_price_data(
        retention_days: int = RETENTION_DAYS
        ) -> datetime | None:
    """
    Update local price data from the ENTSO-E API up to now, cleans up data older than <retention_days> days ago.
    """
    logger.info("\n[Day-Ahead Price Data Update]")
    data_storage.init_raw_db()

    # 1. Load local data
    local = data_storage.read_prices()
    if local:
        last_timestamp = local[-1]["date_heure"]
        logger.info(f"Local data - Last timestamp: {last_timestamp}")
    else:
        last_timestamp = None
        logger.info("No existing price data found.")

    # 2. Determine download window
    now = floor_dt(datetime.now(timezone.utc))
    if last_timestamp is None:
        start = now - timedelta(days=retention_days)
    else:
        start = last_timestamp + timedelta(minutes=15)
    end = now + timedelta(days=2)  # overshoot to include the next day entirely
    logger.info(f"Attempting to download from {start} to {end}")

    # 3. Download from ENTSO-E REST API
    eic = COUNTRY_EIC.get(COUNTRY_CODE, COUNTRY_CODE)
    params = {
        "securityToken": ENTSOE_API_KEY,
        "documentType": "A44",
        "in_Domain": eic,
        "out_Domain": eic,
        "periodStart": start.strftime("%Y%m%d%H%M"),
        "periodEnd": end.strftime("%Y%m%d%H%M"),
    }

    try:
        resp = httpx.get(ENTSOE_API_URL, params=params, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        # 400 with "No matching data" means data is already up to date
        if e.response.status_code == 400 and "No matching data" in e.response.text:
            logger.info("Data already up to date. Nothing to download.")
            return last_timestamp
        logger.error(f"Error when fetching price data: {e!r}")
        return last_timestamp
    except Exception as e:
        logger.error(f"Error when fetching price data: {e!r}")
        return last_timestamp

    new_data = _parse_entsoe_prices(resp.text)
    if not new_data:
        logger.info("No new price data parsed from response.")
        return last_timestamp

    logger.info(f"Downloaded data from {new_data[0]['date_heure']} to {new_data[-1]['date_heure']}")

    # 4. Upsert (SQLite handles dedup)
    data_storage.upsert_prices(new_data)

    # 5. Remove old data
    limit = now - timedelta(days=retention_days)
    data_storage.delete_prices_before(limit)
    logger.info("Update completed.")

    # 6. Return the last timestamp with complete data
    all_data = data_storage.read_prices()
    all_data = trim_trailing_nans(all_data, cols=["price"])
    if not all_data:
        return None
    return all_data[-1]["date_heure"]


def last_ts_prices() -> datetime:
    ts = data_storage.last_ts_prices()
    if ts is None:
        return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    return ts


def should_update_prices(
        last_timestamp: datetime = None,
        min_foresight_prices: int = MIN_FORESIGHT_PRICES
        ) -> bool:
    if last_timestamp is None:
        last_timestamp = last_ts_prices()
    now = datetime.now(timezone.utc)
    return last_timestamp < (now + timedelta(hours=min_foresight_prices))


def last_ts_eco2mix() -> datetime:
    data_storage.init_raw_db()
    local = data_storage.read_eco2mix()
    local = trim_trailing_nans(local, cols=COLS_TRIM)
    if not local:
        return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    return local[-1]["date_heure"]


def should_update_eco2mix(
        last_timestamp: datetime = None,
        freq_update_eco2mix: int = FREQ_UPDATE_ECO2MIX
        ) -> bool:
    if last_timestamp is None:
        last_timestamp = last_ts_eco2mix()
    now = datetime.now(timezone.utc)
    return last_timestamp < (now - timedelta(minutes=freq_update_eco2mix))
