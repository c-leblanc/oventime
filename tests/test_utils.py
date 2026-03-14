import pandas as pd
import numpy as np
import pytest

from oventime.utils import time_interpreter, to_epoch, to_utc_timestamp, trim_trailing_nans

def test_trim_trailing_nans():
    df = pd.DataFrame({"a":[1,2,np.nan,np.nan]})
    res = trim_trailing_nans(df)
    assert len(res) == 2
    assert res["a"].tolist() == [1, 2]

def test_to_epoch_int_timestamp_iso():
    assert to_epoch(1609459200) == 1609459200
    ts = pd.Timestamp("2021-01-01T00:00:00Z")
    assert to_epoch(ts) == 1609459200
    assert to_epoch("2021-01-01T00:00:00Z") == 1609459200

def test_to_utc_timestamp_epoch_and_timestamp():
    assert to_utc_timestamp(1609459200) == pd.Timestamp("2021-01-01T00:00:00Z")
    ts = pd.Timestamp("2021-01-01T02:00:00+02:00")
    assert to_utc_timestamp(ts) == pd.Timestamp("2021-01-01T00:00:00+00:00")

def test_time_interpreter_none_and_string():
    assert time_interpreter(None) is None
    ts = time_interpreter("2021-01-01 00:00")
    assert isinstance(ts, pd.Timestamp)
    assert ts.tzinfo is not None

def test_to_epoch_invalid_type():
    with pytest.raises(TypeError):
        to_epoch(object())
