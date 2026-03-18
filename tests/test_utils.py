import math
from datetime import datetime, timezone
import pytest

from oventime.utils import time_interpreter, to_epoch, to_utc_timestamp, trim_trailing_nans


def test_trim_trailing_nans():
    rows = [{"a": 1.0}, {"a": 2.0}, {"a": float("nan")}, {"a": float("nan")}]
    res = trim_trailing_nans(rows)
    assert len(res) == 2
    assert res[0]["a"] == 1.0
    assert res[1]["a"] == 2.0


def test_to_epoch_int_timestamp_iso():
    assert to_epoch(1609459200) == 1609459200
    ts = datetime(2021, 1, 1, tzinfo=timezone.utc)
    assert to_epoch(ts) == 1609459200
    assert to_epoch("2021-01-01T00:00:00Z") == 1609459200


def test_to_utc_timestamp_epoch_and_timestamp():
    assert to_utc_timestamp(1609459200) == datetime(2021, 1, 1, tzinfo=timezone.utc)
    ts = datetime(2021, 1, 1, 2, 0, 0, tzinfo=timezone(offset=__import__('datetime').timedelta(hours=2)))
    assert to_utc_timestamp(ts) == datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_time_interpreter_none_and_string():
    assert time_interpreter(None) is None
    ts = time_interpreter("2021-01-01 00:00")
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None


def test_to_epoch_invalid_type():
    with pytest.raises(TypeError):
        to_epoch(object())
