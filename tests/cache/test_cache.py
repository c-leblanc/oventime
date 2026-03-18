import sqlite3
import time
import json
from datetime import datetime, timezone, timedelta
import pytest

from oventime.cache import cache
from oventime.utils import floor_dt
from pathlib import Path


def make_output(now):
    return {
        "time": now,
        "status": "ok",
        "score": 42.5,
        "nuclear_bonus": 0.0,
        "ocgt_malus": 0.0,
        "gasCCG_use_rate": 0.1,
        "gasCCG_phase": 0.1,
        "storage_phase": 0.2,
        "storage_use_rate": 0.2,
        "nuclear_use_rate": 0.5,
        "nextwind_start": now,
        "nextwind_end": now + timedelta(minutes=15),
        "nextwind_method": "otsu"
    }


def test_save_and_get_fulldiag(tmp_path):
    db_path = tmp_path / "cache.sqlite"
    cache.DB_PATH = db_path
    cache.init_db()

    now = floor_dt(datetime.now(timezone.utc))
    out = make_output(now)
    cache.save(out, source_version="testv")

    fulldiag = cache.get_fulldiag()
    assert fulldiag is not None
    assert fulldiag["status"] == "ok"
    assert "details" in fulldiag
    assert fulldiag["details"]["gasCCG_use_rate"] == pytest.approx(0.1)


def test_get_status_and_nextwindow(tmp_path):
    db_path = tmp_path / "cache.sqlite"
    cache.DB_PATH = db_path
    cache.init_db()

    now = floor_dt(datetime.now(timezone.utc))
    out = make_output(now)
    cache.save(out)

    status = cache.get_status()
    assert status is not None
    assert status["status"] == "ok"

    nextw = cache.get_nextwindow()
    assert nextw is not None
    assert "nextwind_start" in nextw
    assert "nextwind_end" in nextw


def test_tsubs_add_remove(tmp_path):
    db_path = tmp_path / "cache.sqlite"
    cache.DB_PATH = db_path
    cache.init_db()

    cache.add_tsubs(123456)
    subs = cache.get_tsubs()
    assert 123456 in subs

    cache.remove_tsubs(123456)
    subs2 = cache.get_tsubs()
    assert 123456 not in subs2


def test_wsubs_add_remove(tmp_path):
    db_path = tmp_path / "cache.sqlite"
    cache.DB_PATH = db_path
    cache.init_db()

    ep = "https://example.com/endpoint"
    sub = {"endpoint": ep, "keys": {"p256dh": "aaa", "auth": "bbb"}}
    cache.add_wsubs(ep, sub)

    wsubs = cache.get_wsubs()
    assert ep in wsubs
    assert wsubs[ep]["keys"]["auth"] == "bbb"

    cache.remove_wsubs(ep)
    wsubs2 = cache.get_wsubs()
    assert ep not in wsubs2
