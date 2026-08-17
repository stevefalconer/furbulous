"""Decode vendor errorReportEvent.

Codes are a bitfield. Live 2026-08-16 (three boxes):

- **16** documented waste-full; **32** live-verified full (Upstairs zvb-114).
- **512** = lid / cover off (not “communication error”).
- **128** documented cover; lid-off did **not** set 128.
- **64** is **not** drawer-out (physical drawer-out stayed 0). 64 appeared
  only with **524288** during a jammed trash door (screen Device Failure E4).
- **4096** is a brief pour flash, not full.
"""
from __future__ import annotations

from typing import Any

from .const import ERROR_CODES
from .entity import extract_prop_value

ERROR_WASTE_FULL = 16
ERROR_WASTE_FULL_ALT = 32
ERROR_MECHANISM = 64
ERROR_COVER_DOC = 128
ERROR_LID_OFF = 512
ERROR_LITTER_POUR = 4096
ERROR_TRASH_DOOR = 524288

WASTE_FULL_MASK = ERROR_WASTE_FULL | ERROR_WASTE_FULL_ALT
COVER_MASK = ERROR_COVER_DOC | ERROR_LID_OFF

# Walk known bits; leftovers are labeled "Error {n}".
_BIT_ORDER = (
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
    512,
    4096,
    524288,
)


def parse_error_code(raw: Any) -> int | None:
    """Return the integer errorReportEvent value, or None."""
    value = extract_prop_value(raw)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def has_error_bit(raw: Any, mask: int) -> bool:
    """True when any bit in mask is set."""
    code = parse_error_code(raw)
    if code is None:
        return False
    return (code & mask) != 0


def is_waste_full(raw: Any) -> bool:
    """True when the box reports a full waste bag (16 and/or 32)."""
    return has_error_bit(raw, WASTE_FULL_MASK)


def is_drawer_out(raw: Any) -> bool:
    """Drawer-out is not published on the cloud (live pull stayed 0)."""
    del raw
    return False


def is_cover_open(raw: Any) -> bool:
    """True for documented cover (128) or live lid-off (512)."""
    return has_error_bit(raw, COVER_MASK)


def is_trash_door_blocked(raw: Any) -> bool:
    """True for trash-door jam / Device Failure E4 (bit 524288)."""
    return has_error_bit(raw, ERROR_TRASH_DOOR)


def describe_error(raw: Any) -> str:
    """Human-readable error; combined bits are joined and de-duplicated."""
    code = parse_error_code(raw)
    if code is None:
        return "-"
    if code == 0:
        return ERROR_CODES[0]
    labels: list[str] = []
    seen: set[str] = set()
    skip_64 = bool(code & ERROR_TRASH_DOOR)
    for bit in _BIT_ORDER:
        if bit == ERROR_MECHANISM and skip_64:
            continue
        if code & bit:
            label = ERROR_CODES.get(bit, f"Error {bit}")
            if label not in seen:
                seen.add(label)
                labels.append(label)
    leftover = code
    for bit in _BIT_ORDER:
        leftover &= ~bit
    extra = 1
    while leftover and extra <= leftover:
        if leftover & extra:
            label = f"Error {extra}"
            if label not in seen:
                seen.add(label)
                labels.append(label)
        extra <<= 1
    if labels:
        return "; ".join(labels)
    return f"Error {code}"
