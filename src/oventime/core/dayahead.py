import math
import logging
from datetime import datetime, timezone, timedelta

from oventime.config import WINDOW_RANGE, WINDOW_METHOD, OTSU_SEVERITY
from oventime.utils import to_utc_timestamp, to_epoch, floor_dt
from oventime.input import data_storage

logger = logging.getLogger(__name__)


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


# ── Timeline ternaire ────────────────────────────────────

_STATUS_TO_COLOR = {
    "leaf": "green",
    "green": "green",
    "orange": "orange",
    "red": "red",
    "fire": "red",
}


def price_status_thresholds(now: datetime, lookback_hours: int = 48):
    """
    Compute price thresholds for green/orange/red classification
    by cross-referencing historical prices with cached eco2mix statuses.

    Returns (threshold_green_orange, threshold_orange_red).
    """
    from oventime.cache.cache import get_connection

    start = now - timedelta(hours=lookback_hours)

    # Read cached statuses (ts is epoch)
    start_epoch = to_epoch(start)
    now_epoch = to_epoch(now)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, status FROM cache WHERE ts >= ? AND ts <= ? ORDER BY ts",
        (start_epoch, now_epoch),
    )
    cache_rows = cur.fetchall()
    conn.close()

    if not cache_rows:
        logger.warning("No cached statuses found for threshold computation.")
        return None

    # Read historical prices
    hist_prices = data_storage.read_prices(start=start, end=now)
    price_by_epoch = {to_epoch(r["date_heure"]): r["price"] for r in hist_prices if r["price"] is not None}

    # Pair: for each cache entry, find matching price
    green_prices = []
    orange_prices = []
    red_prices = []

    for ts, status in cache_rows:
        price = price_by_epoch.get(ts)
        if price is None:
            continue
        color = _STATUS_TO_COLOR.get(status)
        if color == "green":
            green_prices.append(price)
        elif color == "orange":
            orange_prices.append(price)
        elif color == "red":
            red_prices.append(price)

    all_paired_prices = green_prices + orange_prices + red_prices

    if not all_paired_prices:
        return None

    # Compute thresholds using medians (robust to overlapping distributions)
    def _median(lst):
        s = sorted(lst)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2

    if green_prices and orange_prices:
        t1 = (_median(green_prices) + _median(orange_prices)) / 2
    elif green_prices:
        t1 = max(green_prices) # No orange observed: above the max green price becomes orange
    elif orange_prices:
        t1 = min(orange_prices) # No green price observed: below the min orange price becomes green
    else:
        t1 = min(red_prices)/2 # No green/orange price observed: below half the min red price becomes green

    if orange_prices and red_prices:
        t2 = (_median(orange_prices) + _median(red_prices)) / 2
    elif orange_prices:
        t2 = max(orange_prices) # No red observed: above the max price for orange becomes red
    elif red_prices:
        t2 = min(red_prices) # No orange observed: below the min price for red becomes orange
    else:
        t2 = 2*t1  # No orange/red observed: twice the max observed becomes red

    # Ensure t1 <= t2
    if t1 > t2:
        t1, t2 = t2, t1

    return t1, t2


def timeline_output(now: datetime = None):
    """
    Compute a ternary-colored timeline of future price slots.
    Returns list[dict] with {"date_heure": datetime, "color": str}.
    Returns None if thresholds or prices are unavailable.
    """
    data_storage.init_raw_db()

    if now is None:
        now = datetime.now(timezone.utc)
    now = floor_dt(to_utc_timestamp(now))

    thresholds = price_status_thresholds(now)
    if thresholds is None:
        logger.warning("Cannot compute timeline: no price/status pairs available.")
        return None

    t1, t2 = thresholds

    # Read future prices (next 12h)
    future_prices = data_storage.read_prices(start=now, end=now + timedelta(hours=12))

    if not future_prices:
        logger.warning("Cannot compute timeline: no future prices available.")
        return None

    slots = []
    for row in future_prices:
        price = row["price"]
        if price is None:
            color = "orange"  # default if price missing
        elif price <= t1:
            color = "green"
        elif price <= t2:
            color = "orange"
        else:
            color = "red"
        slots.append({"date_heure": row["date_heure"], "color": color, "price": price})

    return {"slots": slots, "threshold_go": t1, "threshold_or": t2}
