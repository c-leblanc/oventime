import pandas as pd
from typing import Union, List

import oventime.input.data_processing as data_processing
from oventime.config import RETENTION_DAYS, TIMEZONE


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

def status_from_score(score: float):
    status = "Unknown"
    if score>100: status="leaf"
    elif score>70: status="green"
    elif score>30: status="orange"
    elif score>0: status="red"
    else: status="fire"
    return status

def output(target_time: pd.Timestamp = None):
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
        - status (categorical derived from score)
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

    status = status_from_score(score)

    # Return full diagnostic bundle
    return {
        "time": target_time,
        "status": status,
        "score": score,
        "nuclear_bonus": nuclear_bonus,
        "ocgt_malus": ocgt_malus,
        "gasCCG_use_rate": gasCCG_use_rate,
        "gasCCG_phase": gasCCG_use_rate,
        "storage_phase": storage_phase,
        "storage_use_rate": storage_use_rate,
        "nuclear_use_rate": nuclear_use_rate,
    }



if __name__ == "__main__":
    print(output())
    #print(cycle_whereat(["STORAGE"], pd.Timestamp("2025-12-18 09:00", tz="UTC"), data=data_processing.init_data(), window=7*24*4, mode="min_to_max"))

