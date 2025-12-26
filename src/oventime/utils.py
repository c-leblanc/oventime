import dateparser
import pandas as pd
from typing import Union
import re

from oventime.config import TIMEZONE

ISO_REGEX = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)?$"

def time_interpreter(time_str, tz=TIMEZONE, freq="15min"):
    """
    Parse une chaîne en pd.Timestamp UTC, arrondie à `freq`.
    - accepte str | pd.Timestamp | datetime | None (retourne None)
    - localise en 'tz' si naive, convertit en UTC
    """
    if time_str is None:
        return None

    try:
        # If already a Timestamp / datetime, normalize directly
        if isinstance(time_str, pd.Timestamp):
            ts = time_str
        else:
            # allow datetime too
            from datetime import datetime
            if isinstance(time_str, datetime):
                ts = pd.Timestamp(time_str)
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
                ts = pd.Timestamp(dt)

        # Ensure timezone-aware and convert to UTC
        if ts.tzinfo is None:
            ts = ts.tz_localize(tz)
        else:
            ts = ts.tz_convert(tz)

        ts_utc = ts.tz_convert("UTC").floor(freq)
        return ts_utc

    except Exception:
        raise ValueError(
            f"Format d'heure invalide : {time_str}\nExemples valides : 9, 9am, 21:30, hier 9am, 25/12 14h, ..."
        )


def to_epoch(target_time: Union[int, float, str, pd.Timestamp]) -> int:
    """
    Convert various time inputs to epoch seconds (UTC).

    Accepted inputs:
    - int / float        → assumed epoch seconds
    - pd.Timestamp       → converted to UTC if needed
    - str                → parsed

    Returns
    -------
    int
        Epoch timestamp (seconds, UTC)
    """
    # 1. Epoch already
    if isinstance(target_time, (int, float)):
        return int(target_time)

    # 2. String → pandas
    if isinstance(target_time, str):
        # 1️⃣ Parser robuste (ISO + quasi tout le reste)
        try:
            target_time = pd.to_datetime(target_time, utc=True)
        except Exception:
            # 2️⃣ Langage naturel
            target_time = time_interpreter(target_time)

    # 3. pandas Timestamp -> epoch
    if isinstance(target_time, pd.Timestamp):
        if target_time.tzinfo is None:
            target_time = target_time.tz_localize("UTC")
        else:
            target_time = target_time.tz_convert("UTC")
        return int(target_time.timestamp())

    raise TypeError(
        "target_time must be None, int, float, str or pd.Timestamp "
        f"(got {type(target_time)})"
    )


def to_utc_timestamp(
    target_time: Union[int, float, str, pd.Timestamp]
) -> pd.Timestamp:
    """
    Convert various time inputs to a UTC Timestamp.

    Accepted inputs:
    - int / float        → epoch seconds (UTC)
    - pd.Timestamp       → converted if needed
    - str                → parsed

    Returns
    -------
    pd.Timestamp
        Timezone-aware timestamp in local timezone
    """

    # 1. Epoch → UTC
    if isinstance(target_time, (int, float)):
        return pd.to_datetime(target_time, unit="s", utc=True)

    # 2. pandas Timestamp
    if isinstance(target_time, pd.Timestamp):
        if target_time.tzinfo is None:
            return target_time.tz_localize("UTC")
        else:
            return target_time

    # 3. String
    # String
    if isinstance(target_time, str):
        # 1️⃣ Parser robuste (ISO + quasi tout le reste)
        try:
            return pd.to_datetime(target_time, utc=True)
        except Exception:
            # 2️⃣ Langage naturel
            return time_interpreter(target_time)

    raise TypeError(
        "target_time must be int, float, str or pd.Timestamp "
        f"(got {type(target_time)})"
    )


