import pytest
from oventime.core.dayahead import optimal_threshold_otsu


def test_optimal_threshold_otsu_basic_split():
    values = [10.0] * 20 + [50.0] * 30
    tau = optimal_threshold_otsu(values, severity=1.0)
    assert 10.0 <= tau < 50.0


def test_optimal_threshold_otsu_empty():
    with pytest.raises(ValueError):
        optimal_threshold_otsu([])
