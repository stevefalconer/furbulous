"""Cloud device time helpers — LocalTime packing and property ``time`` stamps.

Verified against docs/api captures (2026-08-15/16):

- ``LocalTime`` packs device **calendar date** (not time-of-day):
  ``(day << 24) | (month << 16) | ((year % 100) << 8) | flag`` with flag=1.
- Property wrappers may include ``time`` in **milliseconds** since epoch.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class LocalDate:
    """Decoded device-local calendar date from ``LocalTime``."""

    year: int
    month: int
    day: int
    flag: int = 1

    @property
    def day_key(self) -> str:
        """Stable YYYY-MM-DD key for day-rollover comparisons."""
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"

    def as_date(self) -> date:
        return date(self.year, self.month, self.day)


def decode_local_time(raw: Any) -> LocalDate | None:
    """Decode ``LocalTime`` integer into a calendar date.

    Returns None if missing/unparseable or fields look invalid.
    """
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    day = (value >> 24) & 0xFF
    month = (value >> 16) & 0xFF
    year_2 = (value >> 8) & 0xFF
    flag = value & 0xFF
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    # Captures use 26 for 2026; accept 00–99 → 2000–2099.
    year = 2000 + year_2 if year_2 < 100 else year_2
    if year < 2000 or year > 2100:
        return None
    try:
        date(year, month, day)  # validate calendar
    except ValueError:
        return None
    return LocalDate(year=year, month=month, day=day, flag=flag)


def encode_local_time(year: int, month: int, day: int, flag: int = 1) -> int:
    """Encode a calendar date to the vendor ``LocalTime`` packing (tests)."""
    return (day << 24) | (month << 16) | ((year % 100) << 8) | (flag & 0xFF)


def local_time_day_key(raw: Any) -> str | None:
    """Return YYYY-MM-DD from a raw ``LocalTime`` value, or None."""
    decoded = decode_local_time(raw)
    return decoded.day_key if decoded else None


def prop_time_unix(raw: Any) -> float | None:
    """Normalize a property ``time`` field to unix seconds.

    Vendor captures use milliseconds (e.g. 1.786e12). Values already in
    seconds (~1.7e9) are left as-is.
    """
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    # ms since epoch are > ~3e10 for years after 1970*1000
    if value > 1e12:
        value = value / 1000.0
    return value


def sane_event_ts(
    candidate: float | None,
    *,
    now: float,
    max_future_s: float = 120.0,
    max_age_s: float = 90 * 86400.0,
) -> float | None:
    """Accept a cloud timestamp only if it is plausible vs wall clock."""
    if candidate is None:
        return None
    if candidate > now + max_future_s:
        return None
    if candidate < now - max_age_s:
        return None
    return candidate
