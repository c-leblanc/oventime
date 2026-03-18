import math
from pathlib import Path

from oventime.config import DATA_DIR
from oventime.input import data_storage

_cache = {"data": None, "mtime": None}

AGGREGATED_COLS = ["RENEWABLE", "NUCLEAR", "STORAGE", "GAS_CCG", "GAS_TAC", "OTHER"]


def _safe_sum(*values):
    """Sum values, returning None if any is None or NaN."""
    for v in values:
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
    return sum(values)


def init_data() -> list[dict]:
    data_storage.init_raw_db()
    db_path = data_storage.RAW_DB_PATH

    if not db_path.exists():
        return []

    current_mtime = db_path.stat().st_mtime
    if _cache["data"] is not None and _cache["mtime"] == current_mtime:
        return _cache["data"]

    rows = data_storage.read_eco2mix()

    result = []
    for row in rows:
        agg = {"date_heure": row["date_heure"]}
        agg["RENEWABLE"] = _safe_sum(
            row.get("eolien"), row.get("solaire"), row.get("hydraulique_fil_eau_eclusee")
        )
        agg["NUCLEAR"] = row.get("nucleaire")
        agg["STORAGE"] = _safe_sum(
            row.get("hydraulique_lacs"), row.get("hydraulique_step_turbinage"),
            row.get("pompage"), row.get("destockage_batterie"), row.get("stockage_batterie")
        )
        agg["GAS_CCG"] = row.get("gaz_ccg")
        agg["GAS_TAC"] = row.get("gaz_tac")
        agg["OTHER"] = _safe_sum(
            row.get("charbon"), row.get("gaz_autres"), row.get("fioul_tac"),
            row.get("fioul_autres"), row.get("gaz_cogen"), row.get("fioul_cogen"),
            row.get("bioenergies")
        )

        # dropna(how="any") equivalent: skip rows where any aggregated value is None
        if any(agg.get(c) is None for c in AGGREGATED_COLS):
            continue

        result.append(agg)

    _cache["data"] = result
    _cache["mtime"] = current_mtime
    return result
