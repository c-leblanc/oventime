import pandas as pd
import numpy as np
from oventime.core.dayahead import optimal_threshold_otsu

def test_optimal_threshold_otsu_basic_split():
    values = np.concatenate([np.full(20, 10.0), np.full(30, 50.0)])
    s = pd.Series(values)
    tau = optimal_threshold_otsu(s, severity=1.0)
    assert 10.0 <= tau < 50.0

def test_optimal_threshold_otsu_empty():
    import pytest
    with pytest.raises(ValueError):
        optimal_threshold_otsu(pd.Series([], dtype=float))
