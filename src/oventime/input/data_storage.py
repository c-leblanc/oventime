import sqlite3
import math
from datetime import datetime, timezone
from pathlib import Path

from oventime.config import DATA_DIR

RAW_DB_PATH = Path(DATA_DIR / "raw.sqlite")

ECO2MIX_COLS = [
    "eolien", "solaire", "hydraulique_fil_eau_eclusee",
    "nucleaire",
    "hydraulique_lacs", "hydraulique_step_turbinage",
    "pompage", "destockage_batterie", "stockage_batterie",
    "gaz_ccg", "gaz_tac",
    "charbon", "gaz_autres", "fioul_tac", "fioul_autres",
    "gaz_cogen", "fioul_cogen", "bioenergies",
]


def _get_conn() -> sqlite3.Connection:
    RAW_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(RAW_DB_PATH))
    return conn


def init_raw_db():
    cols_sql = ",\n    ".join(f"{c} REAL" for c in ECO2MIX_COLS)
    with _get_conn() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS eco2mix (
                date_heure TEXT PRIMARY KEY,
                {cols_sql}
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS da_prices (
                date_heure TEXT PRIMARY KEY,
                price REAL
            )
        """)


def _dt_to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _safe_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── Eco2mix ──────────────────────────────────────────────

def upsert_eco2mix(rows: list[dict]):
    if not rows:
        return
    cols = ["date_heure"] + ECO2MIX_COLS
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO eco2mix ({','.join(cols)}) VALUES ({placeholders})"
    with _get_conn() as conn:
        conn.executemany(sql, [
            tuple(
                _dt_to_iso(row["date_heure"]) if c == "date_heure" else _safe_float(row.get(c))
                for c in cols
            )
            for row in rows
        ])


def read_eco2mix(start: datetime = None, end: datetime = None) -> list[dict]:
    conditions = []
    params = []
    if start is not None:
        conditions.append("date_heure >= ?")
        params.append(_dt_to_iso(start))
    if end is not None:
        conditions.append("date_heure <= ?")
        params.append(_dt_to_iso(end))

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT date_heure, {','.join(ECO2MIX_COLS)} FROM eco2mix{where} ORDER BY date_heure ASC"

    with _get_conn() as conn:
        cursor = conn.execute(sql, params)
        columns = ["date_heure"] + ECO2MIX_COLS
        rows = []
        for row in cursor:
            d = dict(zip(columns, row))
            d["date_heure"] = _iso_to_dt(d["date_heure"])
            rows.append(d)
        return rows


def last_ts_eco2mix() -> datetime | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT MAX(date_heure) FROM eco2mix").fetchone()
        if row and row[0]:
            return _iso_to_dt(row[0])
    return None


def delete_eco2mix_before(limit: datetime):
    with _get_conn() as conn:
        conn.execute("DELETE FROM eco2mix WHERE date_heure < ?", (_dt_to_iso(limit),))


# ── Day-ahead prices ────────────────────────────────────

def upsert_prices(rows: list[dict]):
    if not rows:
        return
    sql = "INSERT OR REPLACE INTO da_prices (date_heure, price) VALUES (?, ?)"
    with _get_conn() as conn:
        conn.executemany(sql, [
            (_dt_to_iso(row["date_heure"]), _safe_float(row.get("price")))
            for row in rows
        ])


def read_prices(start: datetime = None, end: datetime = None) -> list[dict]:
    conditions = []
    params = []
    if start is not None:
        conditions.append("date_heure >= ?")
        params.append(_dt_to_iso(start))
    if end is not None:
        conditions.append("date_heure <= ?")
        params.append(_dt_to_iso(end))

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT date_heure, price FROM da_prices{where} ORDER BY date_heure ASC"

    with _get_conn() as conn:
        cursor = conn.execute(sql, params)
        rows = []
        for row in cursor:
            rows.append({
                "date_heure": _iso_to_dt(row[0]),
                "price": row[1],
            })
        return rows


def last_ts_prices() -> datetime | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT MAX(date_heure) FROM da_prices").fetchone()
        if row and row[0]:
            return _iso_to_dt(row[0])
    return None


def delete_prices_before(limit: datetime):
    with _get_conn() as conn:
        conn.execute("DELETE FROM da_prices WHERE date_heure < ?", (_dt_to_iso(limit),))
