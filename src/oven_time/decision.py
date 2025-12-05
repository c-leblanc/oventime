from oven_time import processing
import pandas as pd

import pandas as pd
from typing import Union, List


def cycle_whereat(
    tec: List[str],
    target_time: pd.Timestamp,
    data: pd.DataFrame,
    mode: str = "min_to_max",
    window: int = 24
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
        raise ValueError(f"Timestamp {target_time} is not present in the dataset.")

    # ------------------------------------------------------------
    # Extract the time window ending at target_time
    # ------------------------------------------------------------
    idx_target = data.index.get_loc(target_time)
    start_idx = idx_target - window + 1

    # If start index is negative, the requested window exceeds available data
    if start_idx < 0:
        raise ValueError(
            f"Requested window size {window} exceeds available data "
            f"by {-start_idx} rows."
        )

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
    window: int = 24,
    at_time: Union[None, str, pd.Timestamp] = None
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
    data_full = processing.init_data()

    # ------------------------------------------------------------
    # Interpret and harmonize the target time
    # ------------------------------------------------------------
    if at_time is None:
        target_time = data_full.index.max()
    else:
        target_time = pd.Timestamp(at_time)

        if target_time.tzinfo is None:
            # Localize using the dataset's timezone
            target_time = target_time.tz_localize(data_full.index.tz)
        else:
            # Convert to dataset timezone
            target_time = target_time.tz_convert(data_full.index.tz)

        # Align to dataset's granularity (assumed 15min)
        target_time = target_time.floor("15min")

    # Compute the cycle index
    result = cycle_whereat(
        tec=tec,
        target_time=target_time,
        data=data_full,
        mode=mode,
        window=window
    )

    return result[tec[0]] if single else result



def diagnostic(at_time: Union[None, str, pd.Timestamp] = None):
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
    data = processing.init_data()

    # ------------------------------------------------------------
    # Interpret target time
    # ------------------------------------------------------------
    if at_time is None:
        target_time = data.index.max()
    else:
        target_time = pd.Timestamp(at_time)

        if target_time.tzinfo is None:
            target_time = target_time.tz_localize(data.index.tz)
        else:
            target_time = target_time.tz_convert(data.index.tz)

        target_time = target_time.floor("15min")

    # ------------------------------------------------------------
    # Retrieve short-term cycle positions
    # ------------------------------------------------------------
    gasCCG_use_rate = cycle_whereat(
        ["GAS_CCG"], target_time, data, window=24*4, mode="zero_to_max"
    )["GAS_CCG"]

    storage_phase = cycle_whereat(
        ["STORAGE"], target_time, data, window=24*4, mode="min_to_max"
    )["STORAGE"]

    storage_use_rate = cycle_whereat(
        ["STORAGE"], target_time, data, window=24*4, mode="zero_to_max"
    )["STORAGE"]

    nuclear_use_rate = cycle_whereat(
        ["NUCLEAR"], target_time, data, window=6*4, mode="zero_to_max"
    )["NUCLEAR"]

    # ------------------------------------------------------------
    # Compute initial score (looser system = higher score)
    # ------------------------------------------------------------
    score = 100*(1 - gasCCG_use_rate) + 50*(1 - storage_phase)

    # ------------------------------------------------------------
    # Bonus points when nuclear cycling down
    # ------------------------------------------------------------
    if gasCCG_use_rate <= 0.1 and nuclear_use_rate <= 0.995:
            score += (1 - nuclear_use_rate) * 5000  # Bonus for downward nuclear cycling


    # Return full diagnostic bundle
    return {
        "time": target_time,
        "score": score,
        "gasCCG_use_rate": gasCCG_use_rate,
        "gasCCG_phase": gasCCG_use_rate,
        "storage_phase": storage_phase,
        "storage_use_rate": storage_use_rate,
        "nuclear_use_rate": nuclear_use_rate,
    }

if __name__ == "__main__":
    print(diagnostic())

