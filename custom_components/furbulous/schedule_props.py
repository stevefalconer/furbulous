"""Probe vendor properties for eco / night schedule times.

Reverse-engineered surface does not yet document stable schedule write keys.
These helpers **read** common candidate keys when present so HA can show
Eco Mode start/stop (and DND windows) under Configuration when the cloud
returns them. Writes remain app-managed until keys are confirmed via
diagnostics capture.
"""
from __future__ import annotations

from typing import Any

from .entity import extract_prop_value

# Ordered candidates (first hit wins). Captured dumps can extend this list.
ECO_START_KEYS = (
    "masterSleepStartTime",
    "masterSleepTimeStart",
    "sleepStartTime",
    "ecoModeStartTime",
    "ecoStartTime",
    "energySavingStartTime",
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
)
DND_START_KEYS = (
    "disturbStartTime",
    "dndStartTime",
    "nightModeStartTime",
    "doNotDisturbStartTime",
)
DND_STOP_KEYS = (
    "disturbEndTime",
    "disturbStopTime",
    "dndEndTime",
    "dndStopTime",
    "nightModeEndTime",
    "doNotDisturbEndTime",
)


def _format_time_value(raw: Any) -> str | None:
    """Normalize API time into HH:MM (or pass through short strings)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        # Already HH:MM or HH:MM:SS
        if ":" in text:
            parts = text.split(":")
            try:
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
            except (TypeError, ValueError):
                return text
            return text
        # Digits only: HHMM
        if text.isdigit() and len(text) in (3, 4):
            try:
                num = int(text)
                hour, minute = divmod(num, 100)
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
            except (TypeError, ValueError):
                pass
        return text
    if isinstance(raw, (int, float)):
        num = int(raw)
        # Minutes from midnight (0–1439)
        if 0 <= num <= 1439:
            hour, minute = divmod(num, 60)
            return f"{hour:02d}:{minute:02d}"
        # HHMM integer e.g. 2230
        if 0 <= num <= 2359:
            hour, minute = divmod(num, 100)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        return str(num)
    return str(raw)


def first_prop(
    properties: dict[str, Any] | None, keys: tuple[str, ...]
) -> tuple[str | None, str | None]:
    """Return (formatted_value, source_key) for the first matching property."""
    if not properties:
        return None, None
    for key in keys:
        if key not in properties:
            continue
        formatted = _format_time_value(extract_prop_value(properties.get(key)))
        if formatted is not None:
            return formatted, key
    return None, None


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
                continue  # skip visit timers
            val = extract_prop_value(raw)
            if val is not None:
                hits[f"prop_{key}"] = str(val)
    hits["schedule_source"] = "properties" if hits else "app_or_unknown"
    return hits
