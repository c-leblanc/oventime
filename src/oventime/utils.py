import math
from datetime import datetime, timezone
from typing import Union
from zoneinfo import ZoneInfo

import dateparser

from oventime.config import TIMEZONE

ISO_REGEX = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)?$"


def floor_dt(dt: datetime, minutes: int = 15) -> datetime:
    """Floor a datetime to the nearest `minutes` boundary."""
    floored_minute = (dt.minute // minutes) * minutes
    return dt.replace(minute=floored_minute, second=0, microsecond=0)


def time_interpreter(time_str, tz=TIMEZONE, freq=15):
    """
    Parse une chaîne en datetime UTC, arrondie à `freq` minutes.
    - accepte str | datetime | None (retourne None)
    - localise en 'tz' si naive, convertit en UTC
    """
    if time_str is None:
        return None  # Important passthrough (no time argument can mean now)

    try:
        if isinstance(time_str, datetime):
            ts = time_str
        else:
            dt = dateparser.parse(
                time_str,
                settings={
                    "TIMEZONE": tz,
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "DATE_ORDER": "DMY",
                    "PREFER_DATES_FROM": "past",
                },
            )
            if dt is None:
                raise ValueError()
            ts = dt

        # Ensure timezone-aware and convert to UTC
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ZoneInfo(tz))
        else:
            ts = ts.astimezone(ZoneInfo(tz))

        ts_utc = floor_dt(ts.astimezone(timezone.utc), minutes=freq)
        return ts_utc

    except ValueError:
        raise ValueError(
            f"Format d'heure invalide : {time_str}\nExemples valides : 9, 9am, 21:30, hier 9am, 25/12 14h, ..."
        )


def to_epoch(target_time: Union[int, float, str, datetime]) -> int:
    """
    Convert various time inputs to epoch seconds (UTC).

    Accepted inputs:
    - int / float        → assumed epoch seconds
    - datetime           → converted to UTC if needed
    - str                → parsed

    Returns
    -------
    int
        Epoch timestamp (seconds, UTC)
    """
    # 1. Epoch already
    if isinstance(target_time, (int, float)):
        return int(target_time)

    # 2. String → datetime
    if isinstance(target_time, str):
        try:
            target_time = datetime.fromisoformat(target_time)
        except ValueError:
            target_time = time_interpreter(target_time)

    # 3. datetime -> epoch
    if isinstance(target_time, datetime):
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        else:
            target_time = target_time.astimezone(timezone.utc)
        return int(target_time.timestamp())

    raise TypeError(
        "target_time must be None, int, float, str or datetime "
        f"(got {type(target_time)})"
    )


def to_utc_timestamp(
    target_time: Union[int, float, str, datetime]
) -> datetime:
    """
    Convert various time inputs to a UTC datetime.

    Accepted inputs:
    - int / float        → epoch seconds (UTC)
    - datetime           → converted if needed
    - str                → parsed

    Returns
    -------
    datetime
        Timezone-aware datetime in UTC
    """
    if target_time is None: return None

    # 1. Epoch → UTC
    if isinstance(target_time, (int, float)):
        return datetime.fromtimestamp(target_time, tz=timezone.utc)

    # 2. datetime
    if isinstance(target_time, datetime):
        if target_time.tzinfo is None:
            return target_time.replace(tzinfo=timezone.utc)
        else:
            return target_time.astimezone(timezone.utc)

    # 3. String
    if isinstance(target_time, str):
        try:
            return datetime.fromisoformat(target_time).astimezone(timezone.utc)
        except ValueError:
            return time_interpreter(target_time)

    raise TypeError(
        "target_time must be int, float, str or datetime "
        f"(got {type(target_time)})"
    )


def fmt_ts(dt: "datetime | None") -> str:
    """Compact local-time datetime string for logs: DD/MM HH:MM"""
    if dt is None:
        return "—"
    return dt.astimezone(ZoneInfo(TIMEZONE)).strftime("%d/%m %H:%M")


def trim_trailing_nans(rows: list[dict], cols: list = None) -> list[dict]:
    """
    Removes rows with missing values at the end of a list of dicts.
    If cols is specified, only checks those keys for NaN.
    """
    def _has_nan(row, keys):
        for k in keys:
            v = row.get(k)
            if v is None:
                return True
            if isinstance(v, float) and math.isnan(v):
                return True
        return False

    result = list(rows)
    while result:
        check_keys = cols if cols is not None else list(result[-1].keys())
        if _has_nan(result[-1], check_keys):
            result.pop()
        else:
            break
    return result
