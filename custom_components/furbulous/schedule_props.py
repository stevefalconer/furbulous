"""Read/write vendor properties for Screen off and Quiet hours schedules.

The box applies Screen off / Quiet hours only inside the daily start–end window.
HA must be able to set those times (not only the on/off switches).

Write format matches the format last seen on the property when possible:
minutes-from-midnight (0–1439), HHMM int, or ``HH:MM`` string.
"""
from __future__ import annotations

from datetime import time
from typing import Any

from .entity import extract_prop_value

# Preferred write keys first; then common aliases from reverse-engineered dumps.
ECO_START_KEYS = (
    "masterSleepStartTime",
    "masterSleepTimeStart",
    "sleepStartTime",
    "ecoModeStartTime",
    "ecoStartTime",
    "energySavingStartTime",
    "masterSleepOnTime",
    "sleepOnTime",
)
ECO_STOP_KEYS = (
    "masterSleepEndTime",
    "masterSleepTimeEnd",
    "masterSleepStopTime",
    "sleepEndTime",
    "sleepStopTime",
    "ecoModeEndTime",
    "ecoEndTime",
    "ecoStopTime",
    "energySavingEndTime",
    "masterSleepOffTime",
    "sleepOffTime",
)
DND_START_KEYS = (
    "disturbStartTime",
    "dndStartTime",
    "nightModeStartTime",
    "doNotDisturbStartTime",
    "isDisturbStartTime",
    "disturbTimeStart",
)
DND_STOP_KEYS = (
    "disturbEndTime",
    "disturbStopTime",
    "dndEndTime",
    "dndStopTime",
    "nightModeEndTime",
    "doNotDisturbEndTime",
    "isDisturbEndTime",
    "disturbTimeEnd",
)

# Default keys when the cloud has not returned a schedule property yet
DEFAULT_ECO_START_KEY = ECO_START_KEYS[0]
DEFAULT_ECO_STOP_KEY = ECO_STOP_KEYS[0]
DEFAULT_DND_START_KEY = DND_START_KEYS[0]
DEFAULT_DND_STOP_KEY = DND_STOP_KEYS[0]


def _format_time_value(raw: Any) -> str | None:
    """Normalize API time into HH:MM."""
    t = raw_to_time(raw)
    if t is None:
        return None
    return f"{t.hour:02d}:{t.minute:02d}"


def raw_to_time(raw: Any) -> time | None:
    """Parse vendor raw value into datetime.time."""
    if raw is None:
        return None
    if isinstance(raw, time):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if ":" in text:
            parts = text.split(":")
            try:
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return time(hour, minute)
            except (TypeError, ValueError):
                return None
            return None
        if text.isdigit() and len(text) in (3, 4):
            try:
                num = int(text)
                hour, minute = divmod(num, 100)
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return time(hour, minute)
            except (TypeError, ValueError):
                return None
        return None
    if isinstance(raw, (int, float)):
        num = int(raw)
        # Minutes from midnight (0–1439) — most common for these boxes
        if 0 <= num <= 1439:
            hour, minute = divmod(num, 60)
            return time(hour, minute)
        # HHMM integer e.g. 2230
        if 0 <= num <= 2359:
            hour, minute = divmod(num, 100)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
        return None
    return None


def detect_raw_format(raw: Any) -> str:
    """Return format tag: minutes | hhmm | hhmm_str | colon."""
    if raw is None:
        return "minutes"
    if isinstance(raw, str):
        text = raw.strip()
        if ":" in text:
            return "colon"
        if text.isdigit() and len(text) in (3, 4):
            return "hhmm_str"
        return "colon"
    if isinstance(raw, (int, float)):
        num = int(raw)
        if 0 <= num <= 1439:
            return "minutes"
        if 0 <= num <= 2359:
            return "hhmm"
    return "minutes"


def encode_time(value: time, fmt: str = "minutes") -> Any:
    """Encode datetime.time for properties/set."""
    if fmt == "colon":
        return f"{value.hour:02d}:{value.minute:02d}"
    if fmt == "hhmm":
        return value.hour * 100 + value.minute
    if fmt == "hhmm_str":
        return f"{value.hour * 100 + value.minute:04d}"
    # minutes from midnight
    return value.hour * 60 + value.minute


def first_prop(
    properties: dict[str, Any] | None, keys: tuple[str, ...]
) -> tuple[str | None, str | None]:
    """Return (formatted HH:MM, source_key) for the first matching property."""
    t, key = first_prop_time(properties, keys)
    if t is None:
        return None, key
    return f"{t.hour:02d}:{t.minute:02d}", key


def first_prop_time(
    properties: dict[str, Any] | None, keys: tuple[str, ...]
) -> tuple[time | None, str | None]:
    """Return (time, source_key) for the first matching property."""
    if not properties:
        return None, None
    for key in keys:
        if key not in properties:
            continue
        raw = extract_prop_value(properties.get(key))
        parsed = raw_to_time(raw)
        if parsed is not None:
            return parsed, key
    return None, None


def resolve_write_payload(
    properties: dict[str, Any] | None,
    keys: tuple[str, ...],
    default_key: str,
    value: time,
) -> dict[str, Any]:
    """Build ``{property_key: encoded_value}`` for properties/set."""
    props = properties or {}
    # Prefer a key that already exists on the device
    for key in keys:
        if key not in props:
            continue
        raw = extract_prop_value(props.get(key))
        fmt = detect_raw_format(raw)
        return {key: encode_time(value, fmt)}
    # No schedule property yet — write preferred key as minutes-from-midnight
    return {default_key: encode_time(value, "minutes")}


def schedule_probe_attributes(properties: dict[str, Any] | None) -> dict[str, str]:
    """Extra attributes for diagnostics: any schedule-looking property keys."""
    if not properties:
        return {"schedule_source": "app_or_unknown"}
    hits: dict[str, str] = {}
    for key, raw in properties.items():
        low = key.lower()
        if any(
            token in low
            for token in ("sleep", "eco", "disturb", "dnd", "night", "time")
        ):
            if "timer" in low and "everyday" in low:
                continue
            val = extract_prop_value(raw)
            if val is not None:
                hits[f"prop_{key}"] = str(val)
    hits["schedule_source"] = "properties" if hits else "app_or_unknown"
    return hits
