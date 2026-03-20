import httpx
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

from oventime.config import RETENTION_DAYS, FREQ_UPDATE_ECO2MIX, MIN_FORESIGHT_PRICES, COUNTRY_CODE, ENTSOE_API_KEY
from oventime.utils import trim_trailing_nans, floor_dt, fmt_ts
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
    data_storage.init_raw_db()

    # 1. Load existing data
    local = data_storage.read_eco2mix()
    local = trim_trailing_nans(local, cols=COLS_TRIM)
    prev_ts = local[-1]["date_heure"] if local else None

    # 2. Determine download window
    now = floor_dt(datetime.now(timezone.utc))
    earliest_needed = now - timedelta(days=retention_days)

    if prev_ts is None:
        start = earliest_needed
    else:
        oldest_local = local[0]["date_heure"] if local else None
        if oldest_local is None or oldest_local > earliest_needed + timedelta(hours=1):
            start = earliest_needed
            logger.warning(f"[eco2mix] Historique incomplet (oldest={fmt_ts(oldest_local)}), retéléchargement depuis {fmt_ts(start)}")
        else:
            start = prev_ts + timedelta(minutes=15)

    if start >= now:
        logger.info(f"[eco2mix] À jour — last={fmt_ts(prev_ts)}")
        return prev_ts

    # 3. Download missing data
    all_new = []
    while start < now:
        try:
            new_data = eco2mix_rows(start=start, end=now)
        except Exception as e:
            logger.error(f"[eco2mix] Erreur téléchargement (start={fmt_ts(start)}): {e!r}")
            break

        if not new_data:
            break

        all_new.extend(new_data)
        start = new_data[-1]["date_heure"] + timedelta(minutes=15)

    if not all_new:
        if not local:
            logger.error("[eco2mix] Aucune donnée disponible.")
            return None
        logger.info(f"[eco2mix] Rien de nouveau — last={fmt_ts(prev_ts)}")
        return prev_ts

    # 4. Upsert new data (SQLite handles dedup via PRIMARY KEY)
    data_storage.upsert_eco2mix(all_new)

    # 5. Remove data older than retention_days
    data_storage.delete_eco2mix_before(now - timedelta(days=retention_days))

    # 6. Return the last timestamp with complete data + log summary
    all_data_raw = data_storage.read_eco2mix()
    all_data = trim_trailing_nans(all_data_raw, cols=COLS_TRIM)
    if not all_data:
        return None
    n_trimmed = len(all_data_raw) - len(all_data)
    dl_str = f"{fmt_ts(all_new[0]['date_heure'])}→{fmt_ts(all_new[-1]['date_heure'])} (+{len(all_new)})"
    logger.info(f"[eco2mix] prev={fmt_ts(prev_ts)} | dl={dl_str} | trim={n_trimmed} | last={fmt_ts(all_data[-1]['date_heure'])}")
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

            # Resolution must be PT15M
            if resolution_el is None or resolution_el.text is None or "15M" not in resolution_el.text:
                raise ValueError(f"Résolution ENTSO-E inattendue : {resolution_el.text if resolution_el is not None else 'None'}")
            resolution_minutes = 15

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
    data_storage.init_raw_db()

    # 1. Load local data
    local = data_storage.read_prices()
    prev_ts = local[-1]["date_heure"] if local else None

    # 2. Determine download window
    now = floor_dt(datetime.now(timezone.utc))
    start = (prev_ts + timedelta(minutes=15)) if prev_ts else (now - timedelta(days=retention_days))
    end = now + timedelta(days=2)  # overshoot to include the next day entirely

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
        if e.response.status_code == 400 and "No matching data" in e.response.text:
            logger.info(f"[prices] À jour — last={fmt_ts(prev_ts)}")
            return prev_ts
        logger.error(f"[prices] Erreur HTTP: {e!r}")
        return prev_ts
    except Exception as e:
        logger.error(f"[prices] Erreur: {e!r}")
        return prev_ts

    new_data = _parse_entsoe_prices(resp.text)
    if not new_data:
        logger.info(f"[prices] Réponse vide — last={fmt_ts(prev_ts)}")
        return prev_ts

    # 4. Upsert (SQLite handles dedup)
    data_storage.upsert_prices(new_data)

    # 5. Remove old data
    data_storage.delete_prices_before(now - timedelta(days=retention_days))

    # 6. Return the last timestamp with complete data + log summary
    all_data_raw = data_storage.read_prices()
    all_data = trim_trailing_nans(all_data_raw, cols=["price"])
    if not all_data:
        return None
    n_trimmed = len(all_data_raw) - len(all_data)
    dl_str = f"{fmt_ts(new_data[0]['date_heure'])}→{fmt_ts(new_data[-1]['date_heure'])} (+{len(new_data)})"
    logger.info(f"[prices] prev={fmt_ts(prev_ts)} | dl={dl_str} | trim={n_trimmed} | last={fmt_ts(all_data[-1]['date_heure'])}")
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
