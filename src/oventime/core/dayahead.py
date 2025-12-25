import numpy as np
import pandas as pd

from oventime.config import PROJECT_ROOT, WINDOW_RANGE, WINDOW_METHOD


def optimal_threshold_otsu(prices, severity=1.0):
    """
    Compute an optimal low-price threshold using an Otsu-like criterion.

    The threshold maximizes the between-class variance between
    low-price and high-price groups.

    Parameters
    ----------
    prices : pd.Series
        Time-indexed price series.
    severity : float >= 0
        Severity parameter.
        - 1.0 : standard Otsu
        - >1  : more selective (lower threshold)
        - <1  : more permissive

    Returns
    -------
    float
        Optimal threshold value.

    Raises
    ------
    ValueError
        If the threshold cannot be determined (e.g. constant or empty series).
    """
    values = prices.dropna().values

    if len(values) == 0:
        raise ValueError("Empty price series: cannot compute Otsu threshold.")

    candidates = np.unique(values)

    best_tau, best_score = None, -np.inf

    for tau in candidates:
        low = values[values <= tau]
        high = values[values > tau]

        # Both groups must be non-empty
        if len(low) == 0 or len(high) == 0:
            continue

        pL = len(low) / len(values)
        pH = 1 - pL

        # Between-class variance
        score = (pL ** (1/severity)) * pH * (low.mean() - high.mean())**2

        if score > best_score:
            best_score, best_tau = score, tau

    if best_tau is None:
        raise ValueError("Unable to determine an Otsu threshold (constant prices).")

    return best_tau

def price_window(
    max_window=pd.Timedelta(hours=WINDOW_RANGE),
    method: str = WINDOW_METHOD,
    severity: float = 1.0,
    relative_low: float = 0.30,
    absolute_low: float = 10
):
    """
    Identify the longest contiguous low-price time window
    within the next `max_window` horizon.

    Parameters
    ----------
    max_window : pd.Timedelta
        Maximum forward-looking time window.
    method : {"otsu", "arbitrary"}
        Method used to determine the low-price threshold.
    relative_low : float
        Relative threshold position (only used if method="arbitrary").
    absolute_low : float
        Absolute minimum price threshold (only used if method="arbitrary").

    Returns
    -------
    (pd.Timestamp, pd.Timestamp, int)
        Start time, end time, window range effectively considered (available prices).

    Raises
    ------
    ValueError
        If no valid low-price window can be identified.
    """

    # ------------------------------------------------------------------
    # 1. Load and truncate price data
    # ------------------------------------------------------------------
    prices = pd.read_parquet(PROJECT_ROOT / "data/raw/DAprices.parquet")["price"]

    now = pd.Timestamp.now(tz="UTC").floor("15min")
    limit = now + max_window

    prices = prices.loc[(prices.index >= now) & (prices.index <= limit)]

    if prices.empty:
        raise ValueError("No price data available in the selected time window.")
    else: eff_window = int((max(prices.index) - now)/pd.Timedelta(hours=1))

    # ------------------------------------------------------------------
    # 2. Determine the low-price threshold
    # ------------------------------------------------------------------
    method = method.lower()

    if method == "arbitrary":
        min_price = prices.min()
        max_price = prices.max()
        relative_threshold = min_price + relative_low * (max_price - min_price)
        threshold = max(relative_threshold, absolute_low)

    elif method == "otsu":
        threshold = optimal_threshold_otsu(prices, severity=severity)

    else:
        raise ValueError(f"Invalid method '{method}' for threshold determination.")

    # ------------------------------------------------------------------
    # 3. Identify the longest contiguous low-price window
    # ------------------------------------------------------------------
    mask = prices <= threshold

    if not mask.any():
        raise ValueError("No prices below the computed threshold.")

    # Identify contiguous True segments
    group_id = (mask.ne(mask.shift(fill_value=False)) & mask).cumsum()

    low_groups = prices[mask].groupby(group_id[mask])

    # Select the longest group (by number of time steps)
    best_group = max(low_groups, key=lambda kv: len(kv[1]))[1]

    start_time = best_group.index[0]
    end_time = best_group.index[-1] + pd.Timedelta(minutes=15)
    #avg_price = best_group.mean()

    return start_time, end_time, eff_window


if __name__ == "__main__":
    print(price_window())
