import sqlite3
import json
from pathlib import Path
import time

from zoneinfo import ZoneInfo

from oventime.utils import to_epoch, to_utc_timestamp
from oventime.config import TIMEZONE, DATA_DIR

DB_PATH = DATA_DIR / "cache.sqlite"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cache (
        ts INTEGER PRIMARY KEY,    
        status TEXT NOT NULL,
        score REAL NOT NULL,
        gasCCG_use_rate REAL,
        storage_phase REAL,
        storage_use_rate REAL,
        nuclear_use_rate REAL,
        nuclear_bonus REAL,
        ocgt_malus REAL,
        nextwind_start INTEGER,
        nextwind_end INTEGER,
        nextwind_method TEXT,        
        source_version TEXT,
        created_at INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_ts
    ON cache (ts)
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        chat_id INTEGER PRIMARY KEY,
        first_seen INTEGER NOT NULL,
        last_activated INTEGER,
        last_deactivated INTEGER,
        active INTEGER NOT NULL DEFAULT 1
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS web_subscribers (
        endpoint TEXT PRIMARY KEY,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        first_seen INTEGER NOT NULL,
        last_activated INTEGER NOT NULL
    );
    """)

    conn.commit()
    conn.close()

#############################################
## Output cache

def save(output, source_version="v1"):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO cache (
            ts, status, score,
            gasCCG_use_rate, storage_phase, storage_use_rate,
            nuclear_use_rate, nuclear_bonus, ocgt_malus, 
            nextwind_start, nextwind_end, nextwind_method,   
            source_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        to_epoch(output["time"]),
        output["status"],
        output["score"],
        output["gasCCG_use_rate"],
        output["storage_phase"],
        output["storage_use_rate"],
        output["nuclear_use_rate"],
        output["nuclear_bonus"],
        output["ocgt_malus"],
        to_epoch(output["nextwind_start"]),
        to_epoch(output["nextwind_end"]),
        output["nextwind_method"],
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
        FROM cache
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (ts,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "ts": to_utc_timestamp(row[0]).astimezone(ZoneInfo(tz_output)),
        "status": row[1],
        "score": row[2],
        "details":{
            "gasCCG_use_rate": row[3],
            "storage_phase": row[4],
            "storage_use_rate": row[5],
            "nuclear_use_rate": row[6],
            "nuclear_bonus": row[7],
            "ocgt_malus": row[8]
            },
        "source_version": row[9],
        "created_at": row[10],
    }


def get_status(target_time=None, tz_output=TIMEZONE):
    if target_time is None: ts = to_epoch(time.time())
    else: ts = to_epoch(target_time)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ts, status
        FROM cache
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (ts,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "ts": to_utc_timestamp(row[0]).astimezone(ZoneInfo(tz_output)),
        "status": row[1]
    }


def get_nextwindow(target_time=None, tz_output=TIMEZONE):
    if target_time is None: ts = to_epoch(time.time())
    else: ts = to_epoch(target_time)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ts, nextwind_start, nextwind_end
        FROM cache
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (ts,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "ts": to_utc_timestamp(row[0]).astimezone(ZoneInfo(tz_output)),
        "nextwind_start": to_utc_timestamp(row[1]).astimezone(ZoneInfo(tz_output)),
        "nextwind_end": to_utc_timestamp(row[2]).astimezone(ZoneInfo(tz_output))
    }

def get_last_ts():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(ts) FROM cache")
    row = cur.fetchone()
    conn.close()
    if row[0] is None:
        return None
    return to_utc_timestamp(row[0])

#############################################
## Web Subscribers (wsubs)

def get_wsubs() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT endpoint, p256dh, auth FROM web_subscribers")
    rows = cur.fetchall()
    conn.close()
    return {
        row[0]: {"endpoint": row[0], "keys": {"p256dh": row[1], "auth": row[2]}}
        for row in rows
    }

def add_wsubs(endpoint: str, sub: dict):
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute("""
        INSERT INTO web_subscribers (endpoint, p256dh, auth, first_seen, last_activated)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(endpoint) DO UPDATE SET
            p256dh = excluded.p256dh,
            auth = excluded.auth,
            last_activated = excluded.last_activated
    """, (endpoint, sub["keys"]["p256dh"], sub["keys"]["auth"], now, now))
    conn.commit()
    conn.close()

def remove_wsubs(endpoint: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM web_subscribers WHERE endpoint = ?", (endpoint,))
    conn.commit()
    conn.close()

#############################################
## Telegram Subscribers (tsubs)

def get_tsubs() -> set:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM subscribers WHERE active = 1")
    rows = cur.fetchall()
    conn.close()
    return {row[0] for row in rows}

def add_tsubs(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute("""
        INSERT INTO subscribers (chat_id, first_seen, last_activated, active)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(chat_id) DO UPDATE SET
            last_activated = excluded.last_activated,
            active = 1
    """, (chat_id, now, now))
    conn.commit()
    conn.close()

def remove_tsubs(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute("""
        UPDATE subscribers
        SET active = 0, last_deactivated = ?
        WHERE chat_id = ?
    """, (now, chat_id))
    conn.commit()
    conn.close()