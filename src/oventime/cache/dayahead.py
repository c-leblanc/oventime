import sqlite3
from pathlib import Path
import time

from oventime.utils import to_utc_timestamp, to_epoch
from oventime.config import TIMEZONE

DB_PATH = Path(__file__).parent / "cache_diag.sqlite"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS dayahead_cache (
        ts INTEGER PRIMARY KEY,    
        nextwind_start INTEGER,
        nextwind_end INTEGER,
        nextwind_method TEXT,        
        source_version TEXT,
        created_at INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_dayahead_ts
    ON dayahead_cache (ts)
    """)

    conn.commit()
    conn.close()



def save(output, source_version="v1"):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO dayahead_cache (
            ts, nextwind_start, nextwind_end, nextwind_method,
            source_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        to_epoch(output["time"]),
        to_epoch(output["nextwind_start"]),
        to_epoch(output["nextwind_end"]),
        output["nextwind_method"],
        source_version,
        int(time.time())
    ))

    conn.commit()
    conn.close()



def get_nextwindow():
    ts = int(time.time())

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ts, nextwind_start, nextwind_end
        FROM dayahead_cache
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (ts,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "ts": to_utc_timestamp(row[0]).tz_convert(TIMEZONE),
        "nextwind_start": to_utc_timestamp(row[1]).tz_convert(TIMEZONE),
        "nextwind_end": to_utc_timestamp(row[2]).tz_convert(TIMEZONE)
    }