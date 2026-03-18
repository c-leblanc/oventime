import math
from datetime import datetime, timezone, timedelta

from oventime.config import WINDOW_RANGE, WINDOW_METHOD, OTSU_SEVERITY
from oventime.utils import to_utc_timestamp, floor_dt
from oventime.input import data_storage


def optimal_threshold_otsu(prices: list[float], severity=OTSU_SEVERITY):
    """
    Compute an optimal low-price threshold using an Otsu-like criterion.

    Parameters
    ----------
    prices : list[float]
        Price values (already filtered for None/NaN).
    severity : float >= 0
        Severity parameter. 1.0 = standard Otsu, >1 = more selective, <1 = more permissive.
    """
    values = prices

    if len(values) == 0:
        raise ValueError("Empty price series: cannot compute Otsu threshold.")

    candidates = sorted(set(values))

    best_tau, best_score = None, -math.inf

    for tau in candidates:
        low = [v for v in values if v <= tau]
        high = [v for v in values if v > tau]

        if len(low) == 0 or len(high) == 0:
            continue

        pL = len(low) / len(values)
        pH = 1 - pL

        mean_low = sum(low) / len(low)
        mean_high = sum(high) / len(high)
        score = (pL ** (1/severity)) * pH * (mean_low - mean_high)**2

        if score > best_score:
            best_score, best_tau = score, tau

    if best_tau is None:
        raise ValueError("Unable to determine an Otsu threshold (constant prices).")

    return best_tau


def price_window(
    now: datetime = None,
    window_range: int = WINDOW_RANGE,
    method: str = WINDOW_METHOD,
    severity: float = OTSU_SEVERITY,
    relative_low: float = 0.30,
    absolute_low: float = 10
):
    """
    Identify the longest contiguous low-price time window
    within the next `window_range` hours.
    """
    data_storage.init_raw_db()

    if now is None:
        now = datetime.now(timezone.utc)
    now = floor_dt(to_utc_timestamp(now))
    limit = now + timedelta(hours=window_range)

    # Load and filter prices
    all_prices = data_storage.read_prices(start=now, end=limit)

    if not all_prices:
        raise ValueError("No price data available in the selected time window.")

    eff_window = int((all_prices[-1]["date_heure"] - now) / timedelta(hours=1))

    # Extract price values (filter None)
    price_values = [r["price"] for r in all_prices if r["price"] is not None]

    if not price_values:
        raise ValueError("No valid price data in the selected time window.")

    # Determine threshold
    method = method.lower()

    if method == "arbitrary":
        min_price = min(price_values)
        max_price = max(price_values)
        relative_threshold = min_price + relative_low * (max_price - min_price)
        threshold = max(relative_threshold, absolute_low)

    elif method == "otsu":
        threshold = optimal_threshold_otsu(price_values, severity=severity)

    else:
        raise ValueError(f"Invalid method '{method}' for threshold determination.")

    # Find contiguous low-price segments
    segments = []
    current_segment = []

    for row in all_prices:
        if row["price"] is not None and row["price"] <= threshold:
            current_segment.append(row)
        else:
            if current_segment:
                segments.append(current_segment)
            current_segment = []
    if current_segment:
        segments.append(current_segment)

    if not segments:
        raise ValueError("No prices below the computed threshold.")

    # Select longest segment
    best = max(segments, key=len)
    start_time = best[0]["date_heure"]
    end_time = best[-1]["date_heure"] + timedelta(minutes=15)

    return {
        "time": now,
        "start_time": start_time,
        "end_time": end_time,
        "eff_window": eff_window,
        "method": method
    }


def output(now: datetime = None):
    pwind = price_window(now=now)
    return {
        "time": pwind["time"],
        "nextwind_start": pwind["start_time"],
        "nextwind_end": pwind["end_time"],
        "nextwind_method": pwind["method"]
    }
