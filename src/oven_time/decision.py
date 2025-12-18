from oven_time import data_processing
from oven_time.config import PROJECT_ROOT, WINDOW_RANGE, RETENTION_DAYS, TIMEZONE

import pandas as pd
import numpy as np
from typing import Union, List


def cycle_whereat(
    tec: List[str],
    target_time: pd.Timestamp,
    data: pd.DataFrame,
    mode: str = "min_to_max",
    window: int = 7*24*4
):
    """
    Compute normalized position of one or several technologies within a
    backward-looking time window ending at `target_time`.

    Two normalization modes are supported:
    - "min_to_max":    (value - min) / (max - min)
    - "zero_to_max":   value / max

    Parameters
    ----------
    tec : list[str]
        Technology names (columns of `data`) for which the index is computed.

    target_time : pd.Timestamp
        Timestamp at which the index is evaluated. Must exist in `data.index`.

    data : pd.DataFrame
        Full dataset containing the technologies as columns and timestamps as index.

    mode : {"min_to_max", "zero_to_max"}
        Normalization method.

    window : int
        Number of historical data points included in the window.
    """

    # Ensure the target timestamp exists in the dataset
    if target_time not in data.index:
        raise ValueError(f"Données absentes pour la date demandée ({target_time.tz_convert(tz=TIMEZONE)}) : "
                         f"veuillez entrer une date comprise entre il y a {RETENTION_DAYS-window//(24*4)} jours et maintenant.")

    # ------------------------------------------------------------
    # Extract the time window ending at target_time
    # ------------------------------------------------------------
    idx_target = data.index.get_loc(target_time)
    start_idx = idx_target - window + 1
    # If start index is negative, the requested window exceeds available data
    if start_idx < 0:
        raise ValueError(f"Données absentes pour la date demandée ({target_time.tz_convert(tz=TIMEZONE)}) : "
                         f"veuillez entrer une date comprise entre il y a {RETENTION_DAYS-window//(24*4)} jours et maintenant.")

    # Slice the relevant window
    window_df = data.iloc[start_idx : idx_target + 1]

    # ------------------------------------------------------------
    # Compute normalized index for each requested technology
    # ------------------------------------------------------------
    result = {}

    for t in tec:
        # Remove missing values to avoid distortions
        series = window_df[t].dropna()

        # If the series has no data, return NaN
        if series.empty:
            result[t] = float("nan")
            continue

        mx = series.max()

        if mode == "min_to_max":
            # Normalization relative to min/max within the window
            mn = series.min()

            if mx == mn:
                # Flat series (constant value) → index is undefined
                result[t] = float("nan")
                continue

            # Position of the last point within the observed range
            result[t] = (series.iloc[-1] - mn) / (mx - mn)

        elif mode == "zero_to_max":
            # Normalization assuming min = 0
            if mx == 0:
                result[t] = float("nan")
                continue

            result[t] = series.iloc[-1] / mx

        else:
            raise ValueError("mode must be 'min_to_max' or 'zero_to_max'")

    return result



def get_cycle_whereat(
    tec: Union[str, List[str]],
    mode: str = "min_to_max",
    window: int = 7*24*4,
    target_time: Union[None, str, pd.Timestamp] = None
):
    """
    Wrapper for `cycle_whereat` that:
    - loads the data,
    - interprets the timestamp input,
    - normalizes technology input,
    - and returns a float instead of a dict when a single technology is used.

    Parameters
    ----------
    tec : str or list[str]
        Technology name(s).

    mode : {"min_to_max", "zero_to_max"}
        Normalization rule (see `cycle_whereat`).

    window : int
        Number of historical points included in the window.

    at_time : None, str, or pd.Timestamp
        Moment of evaluation. If None → latest timestamp available.
        If string → parsed as timestamp.
        Timezones are automatically aligned with the dataset.

    Returns
    -------
    float or dict[str, float]
    """
    # ------------------------------------------------------------
    # Normalize input format to a list, track if a single value is requested
    # ------------------------------------------------------------
    single = False
    if isinstance(tec, str):
        tec = [tec]
        single = True

    # Load entire dataset
    data_full = data_processing.init_data()

    # Compute the cycle index
    result = cycle_whereat(
        tec=tec,
        target_time=target_time,
        data=data_full,
        mode=mode,
        window=window
    )

    return result[tec[0]] if single else result

def diagnostic(target_time: pd.Timestamp = None):
    """
    Provide a global qualitative + quantitative diagnostic of power system tightness,
    based on the current position of:
        - gas generation within its short-term cycle,
        - flexible generation (hydro/storage),
        - nuclear availability.

    The diagnostic is based on the idea that:
        - Low gas usage → loose system
        - High storage phase → storage is discharging → tighter system
        - Nuclear cycling downward → excess electricity

    Parameters
    ----------
    at_time : None, str, or Timestamp
        Moment at which to run the diagnostic. If None → latest timestamp.

    Returns
    -------
    dict
        Contains:
        - time
        - score (higher = looser system)
        - gas_phase
        - storage_phase
        - storage_use_rate
        - nuclear_use_rate
    """

    # ------------------------------------------------------------
    # Load full dataset
    # ------------------------------------------------------------
    data = data_processing.init_data()

    if target_time is None:
        target_time = data.index.max()

    # ------------------------------------------------------------
    # Retrieve short-term cycle positions
    # ------------------------------------------------------------
    gasCCG_use_rate = cycle_whereat(
        ["GAS_CCG"], target_time, data, window=7*24*4, mode="zero_to_max"
    )["GAS_CCG"]

    storage_phase = cycle_whereat(
        ["STORAGE"], target_time, data, window=7*24*4, mode="min_to_max"
    )["STORAGE"]

    storage_use_rate = cycle_whereat(
        ["STORAGE"], target_time, data, window=7*24*4, mode="zero_to_max"
    )["STORAGE"]

    nuclear_use_rate = cycle_whereat(
        ["NUCLEAR"], target_time, data, window=6*4, mode="zero_to_max"
    )["NUCLEAR"]

    # ------------------------------------------------------------
    # Compute initial score between 0 and 100 (looser system = higher score)
    # ------------------------------------------------------------
    score = 100*((2/3)*(1 - gasCCG_use_rate) + (1/3)*(1 - storage_use_rate))

    # ------------------------------------------------------------
    # Bonus points when nuclear cycling down (up to 50)
    # ------------------------------------------------------------
    nuclear_bonus=0
    if gasCCG_use_rate <= 0.1 and nuclear_use_rate <= 0.995:
            nuclear_bonus = min(50,(1 - nuclear_use_rate) * 1000)
            score += nuclear_bonus


    # ------------------------------------------------------------
    # Malus points when OCGT plants are on (typically up to 500 MW, i.e. 50 points)
    # ------------------------------------------------------------
    ocgt_malus=0
    if gasCCG_use_rate >= 0.3:
            ocgt_malus = max(-50,-data.loc[target_time, "GAS_TAC"]/10)
            score += ocgt_malus


    # Return full diagnostic bundle
    return {
        "time": target_time,
        "score": score,
        "nuclear_bonus": nuclear_bonus,
        "ocgt_malus": ocgt_malus,
        "gasCCG_use_rate": gasCCG_use_rate,
        "gasCCG_phase": gasCCG_use_rate,
        "storage_phase": storage_phase,
        "storage_use_rate": storage_use_rate,
        "nuclear_use_rate": nuclear_use_rate,
    }

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
    method: str = "otsu",
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
    #print(price_window())
    print(diagnostic())
    #print(cycle_whereat(["STORAGE"], pd.Timestamp("2025-12-18 09:00", tz="UTC"), data=data_processing.init_data(), window=7*24*4, mode="min_to_max"))

