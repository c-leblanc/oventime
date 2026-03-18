import math
from bisect import bisect_left
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

import oventime.input.data_processing as data_processing
from oventime.config import (RETENTION_DAYS, TIMEZONE,
                             LEAF_THRESHOLD, GREEN_ORANGE_THRESHOLD, ORANGE_RED_THRESHOLD, FIRE_THRESHOLD)


def _find_index(data: list[dict], target_time: datetime) -> int:
    """Find the index of target_time in a sorted list[dict] by date_heure. Raises ValueError if not found."""
    times = [row["date_heure"] for row in data]
    idx = bisect_left(times, target_time)
    if idx < len(times) and times[idx] == target_time:
        return idx
    raise ValueError(
        f"Données absentes pour la date demandée ({target_time.astimezone(ZoneInfo(TIMEZONE))}) : "
        f"veuillez entrer une date comprise entre il y a {RETENTION_DAYS} jours et maintenant."
    )


def cycle_whereat(
    tec: List[str],
    target_time: datetime,
    data: list[dict],
    mode: str = "min_to_max",
    window: int = 7*24*4
):
    """
    Compute normalized position of one or several technologies within a
    backward-looking time window ending at `target_time`.
    """

    idx_target = _find_index(data, target_time)
    start_idx = idx_target - window + 1

    if start_idx < 0:
        raise ValueError(
            f"Données absentes pour la date demandée ({target_time.astimezone(ZoneInfo(TIMEZONE))}) : "
            f"veuillez entrer une date comprise entre il y a {RETENTION_DAYS-window//(24*4)} jours et maintenant."
        )

    window_data = data[start_idx : idx_target + 1]

    result = {}

    for t in tec:
        # Filter out None and NaN
        values = [
            row[t] for row in window_data
            if row.get(t) is not None and not (isinstance(row[t], float) and math.isnan(row[t]))
        ]

        if not values:
            result[t] = float("nan")
            continue

        mx = max(values)

        if mode == "min_to_max":
            mn = min(values)
            if mx == mn:
                result[t] = float("nan")
                continue
            result[t] = (values[-1] - mn) / (mx - mn)

        elif mode == "zero_to_max":
            if mx == 0:
                result[t] = float("nan")
                continue
            result[t] = values[-1] / mx

        else:
            raise ValueError("mode must be 'min_to_max' or 'zero_to_max'")

    return result


def status_from_score(score: float):
    status = "Unknown"
    if score>LEAF_THRESHOLD: status="leaf"
    elif score>GREEN_ORANGE_THRESHOLD: status="green"
    elif score>ORANGE_RED_THRESHOLD: status="orange"
    elif score>FIRE_THRESHOLD: status="red"
    else: status="fire"
    return status


def output(target_time: datetime = None):
    """
    Provide a global qualitative + quantitative diagnostic of power system tightness.
    """

    data = data_processing.init_data()

    if target_time is None:
        target_time = data[-1]["date_heure"]

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

    score = 100*((2/3)*(1 - gasCCG_use_rate) + (1/3)*(1 - storage_use_rate))

    nuclear_bonus=0
    if gasCCG_use_rate <= 0.1 and nuclear_use_rate <= 0.995:
            nuclear_bonus = min(50,(1 - nuclear_use_rate) * 1000)
            score += nuclear_bonus

    ocgt_malus=0
    if gasCCG_use_rate >= 0.3:
            # Find GAS_TAC value at target_time
            idx = _find_index(data, target_time)
            gas_tac = data[idx].get("GAS_TAC", 0) or 0
            ocgt_malus = max(-50, -gas_tac / 10)
            score += ocgt_malus

    status = status_from_score(score)

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
