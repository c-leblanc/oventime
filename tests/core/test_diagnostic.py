import pandas as pd
import numpy as np
from oventime.core.diagnostic import cycle_whereat, status_from_score

def make_index(n=48, start="2025-01-01 00:00"):
    return pd.date_range(start=start, periods=n, freq="15min", tz="UTC")

def test_cycle_whereat_min_to_max():
    idx = make_index(20)
    df = pd.DataFrame({
        "STORAGE": np.linspace(0, 10, len(idx)),
        "GAS_CCG": np.linspace(5, 15, len(idx)),
        "NUCLEAR": np.ones(len(idx))*3
    }, index=idx)
    target = idx[-1]
    res = cycle_whereat(["STORAGE","GAS_CCG"], target, df, mode="min_to_max", window=10)
    assert 0.99 <= res["STORAGE"] <= 1.0
    assert 0.99 <= res["GAS_CCG"] <= 1.0

def test_cycle_whereat_zero_to_max_flat_series():
    idx = make_index(10)
    df = pd.DataFrame({"X": np.zeros(len(idx))}, index=idx)
    target = idx[-1]
    res = cycle_whereat(["X"], target, df, mode="zero_to_max", window=5)
    assert np.isnan(res["X"])

def test_status_from_score_smoke():
    assert status_from_score(1e6) in ("leaf","green","orange","red","fire")
