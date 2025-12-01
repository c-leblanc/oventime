from oven_time import processing
import pandas as pd

import pandas as pd
from typing import Union, List


def cycle_whereat(
    tec: Union[str, List[str]],
    mode: str = "min_to_max",
    window: int = 24,
    at_time: Union[None, str, pd.Timestamp] = None
):
    """
    Compute normalized values for one or several technologies over a time window.

    Two normalization modes are supported:
    - "min_to_max":    (val - min) / (max - min)
    - "zero_to_max":   val / max

    Parameters
    ----------
    tec : str or list[str]
        Technology name(s) to compute the index for.

    mode : {"min_to_max", "zero_to_max"}
        Normalization method:
        - "min_to_max": rescales relative to min and max of the window.
        - "zero_to_max": assumes min=0 and rescales by the maximum value only.

    window : int
        Number of points included in the backward-looking window.
        For example if data is quarter-hourly, window=24 → previous 24 quarters.

    at_time : None, str, or pd.Timestamp
        Timestamp at which the index is evaluated.
        - If None → uses the last timestamp available.
        - Strings are parsed via `pd.Timestamp`.
        - Timezones are harmonized automatically.

    Returns
    -------
    float or dict[str, float]
        If a single technology is passed → return a float.
        Else → return a dictionary mapping each technology to its computed index.
    """

    # ------------------------------------------------------------
    # Normalize input format
    # ------------------------------------------------------------
    single = False
    if isinstance(tec, str):
        tec = [tec]
        single = True

    # ------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------
    data_full = processing.init_data()

    # ------------------------------------------------------------
    # Interpret the target time
    # ------------------------------------------------------------
    if at_time is None:
        target_time = data_full.index.max()
    else:
        target_time = pd.Timestamp(at_time)

        # Align timezone if missing
        if target_time.tzinfo is None:
            target_time = target_time.tz_localize(data_full.index.tz)
        else:
            target_time = target_time.tz_convert(data_full.index.tz)

        # Round to the resolution of the data (assumed 15min)
        target_time = target_time.floor("15min")

    # Ensure target_time exists
    if target_time not in data_full.index:
        raise ValueError(f"Timestamp {target_time} is not present in the dataset.")

    # ------------------------------------------------------------
    # Extract the time window
    # ------------------------------------------------------------
    idx_target = data_full.index.get_loc(target_time)
    start_idx = idx_target - window + 1

    if start_idx < 0:
        raise ValueError(
            f"Requested window size {window} exceeds available data "
            f"by {-start_idx} rows."
        )

    window_df = data_full.iloc[start_idx : idx_target + 1]

    # ------------------------------------------------------------
    # Compute the index
    # ------------------------------------------------------------
    result = {}

    for t in tec:
        series = window_df[t].dropna()

        if series.empty:
            result[t] = float("nan")
            continue

        mx = series.max()

        if mode == "min_to_max":
            mn = series.min()
            if mx == mn:
                # constant series: undefined normalization
                result[t] = float("nan")
                continue
            result[t] = (series.iloc[-1] - mn) / (mx - mn)

        elif mode == "zero_to_max":
            if mx == 0:
                result[t] = float("nan")
                continue
            result[t] = series.iloc[-1] / mx

        else:
            raise ValueError("mode must be 'min_to_max' or 'zero_to_max'")

    return result[tec[0]] if single else result




def diagnostic(time=None):
    """
    Diagnostic of system tightness based on gas usage, flexible generation
    and nuclear availability.

    Parameters
    ----------
    time : None, str or Timestamp
        Moment at which to run the diagnostic. If None → last timestamp available.

    Returns
    -------
    score : float
        Higher = system looser / more surplus electricity
        Lower  = system tighter / high gas usage
    """

    # -------------------------
    #  Retrieve system phases
    # -------------------------
    gas_phase = cycle_whereat("GAS", at_time=time, window=24*4, mode="min_to_max")
    storage_phase = cycle_whereat("STORAGE", at_time=time, window=24*4, mode="min_to_max")
    storage_use_rate = cycle_whereat("STORAGE", at_time=time, window=24*4, mode="zero_to_max")
    nuclear_use_rate = cycle_whereat("NUCLEAR", at_time=time, window=6*4, mode="zero_to_max")

    # -------------------------
    #  Pretty-print diagnostics
    # -------------------------
    print(f"Gas-fired generation is at {gas_phase*100:.0f}% of its range over the past 24h.")
    print(f"Flexible generation (hydro+storage) is at {storage_phase*100:.0f}% of its range over the past 24h.")
    print(f"Flexible generation (hydro+storage) is at {storage_use_rate*100:.0f}% of its recent max output.")
    print(f"Nuclear is at {nuclear_use_rate*100:.1f}% of the recently available capacity.\n")

    # -------------------------
    #  Initial score
    # -------------------------
    # The score rewards "low gas" and "low storage phase" → meaning loose system
    score = 100*(1 - gas_phase) + 50*(1 - storage_phase)

    # -------------------------
    #  Qualitative interpretation
    # -------------------------
    if gas_phase <= 0.1:

        if nuclear_use_rate <= 0.995:
            print("PUMP IT UP! Nuclear seems to be cycling → excess electricity on the grid.")
            score += (1 - nuclear_use_rate) * 5000 # Bonus points for when nuclear is cycling down
        else:
            print("LOOKING GOOD! Gas generation is very low (though nuclear is fully loaded).")

    elif gas_phase <= 0.6:
        print("NOT SO SURE… Gas generation is in a mid-range zone.")

    else:
        print("NOT NOW! Gas generation is in a high phase → system is tight.")

    return score