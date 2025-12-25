import sqlite3
from pathlib import Path
import time

from oventime.utils import to_epoch, to_utc_timestamp
from oventime.config import TIMEZONE

DB_PATH = Path(__file__).parent / "cache_dayahead.sqlite"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_cache (
        ts INTEGER PRIMARY KEY,    
        status TEXT NOT NULL,
        score REAL NOT NULL,
        gasCCG_use_rate REAL,
        storage_phase REAL,
        storage_use_rate REAL,
        nuclear_use_rate REAL,
        nuclear_bonus REAL,
        ocgt_malus REAL,
        source_version TEXT,
        created_at INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_diagnostic_ts
    ON diagnostic_cache (ts)
    """)

    conn.commit()
    conn.close()



def save_diagnostic(d, source_version="v1"):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO diagnostic_cache (
            ts, status, score,
            gasCCG_use_rate, storage_phase, storage_use_rate,
            nuclear_use_rate, nuclear_bonus, ocgt_malus,
            source_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(d["time"].timestamp()),
        d["status"],
        d["score"],
        d["gasCCG_use_rate"],
        d["storage_phase"],
        d["storage_use_rate"],
        d["nuclear_use_rate"],
        d["nuclear_bonus"],
        d["ocgt_malus"],
        source_version,
        int(time.time())
    ))

    conn.commit()
    conn.close()


def get_fulldiag(target_time=None, tz_output=TIMEZONE):
    if target_time is None: ts = int(time.time())
    else: ts = to_epoch(target_time)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            ts, status, score,
            gasCCG_use_rate, storage_phase, storage_use_rate,
            nuclear_use_rate, nuclear_bonus, ocgt_malus,
            source_version, created_at
        FROM diagnostic_cache
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (ts,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "ts": to_utc_timestamp(row[0]).tz_convert(tz_output),
        "status": row[1],
        "score": row[2],
        "gasCCG_use_rate": row[3],
        "storage_phase": row[4],
        "storage_use_rate": row[5],
        "nuclear_use_rate": row[6],
        "nuclear_bonus": row[7],
        "ocgt_malus": row[8],
        "source_version": row[9],
        "created_at": row[10],
    }


def get_status_now():
    ts = int(time.time())

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ts, status
        FROM diagnostic_cache
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (ts,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "ts": row[0],
        "status": row[1]
    }



