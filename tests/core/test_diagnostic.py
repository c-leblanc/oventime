import math
from datetime import datetime, timezone, timedelta
from oventime.core.diagnostic import cycle_whereat, status_from_score


def make_data(n=48, start=None):
    if start is None:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [start + timedelta(minutes=15 * i) for i in range(n)]


def test_cycle_whereat_min_to_max():
    n = 20
    times = make_data(n)
    data = [
        {
            "date_heure": times[i],
            "STORAGE": i * 10 / (n - 1),
            "GAS_CCG": 5 + i * 10 / (n - 1),
            "NUCLEAR": 3.0,
        }
        for i in range(n)
    ]
    target = times[-1]
    res = cycle_whereat(["STORAGE", "GAS_CCG"], target, data, mode="min_to_max", window=10)
    assert 0.99 <= res["STORAGE"] <= 1.0
    assert 0.99 <= res["GAS_CCG"] <= 1.0


def test_cycle_whereat_zero_to_max_flat_series():
    n = 10
    times = make_data(n)
    data = [{"date_heure": times[i], "X": 0.0} for i in range(n)]
    target = times[-1]
    res = cycle_whereat(["X"], target, data, mode="zero_to_max", window=5)
    assert math.isnan(res["X"])


def test_status_from_score_smoke():
    assert status_from_score(1e6) in ("leaf", "green", "orange", "red", "fire")
