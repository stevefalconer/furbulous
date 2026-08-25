"""Sticky bag-chore phases for dashboard status (Cleo capture 2026-08-25).

Cloud ``errorReportEvent`` alone is not enough:

- Full (16|32) → seal
- After seal, full bit often clears to 0 while the sealed bag still sits in
  the drawer — HA must stay on **Bag full / Remove Sealed Bag**
- Brief No Bag (128) during drawer open, then 0 after inflate

Phases:
- ``needs_seal`` — waste full; ask user to seal
- ``needs_remove`` — sealed (or full cleared after pack); remove bag
- ``None`` — no open chore
"""
from __future__ import annotations

from typing import Any

CHORE_NEEDS_SEAL = "needs_seal"
CHORE_NEEDS_REMOVE = "needs_remove"

LABEL_SEAL = "Bag full - seal bag"
LABEL_REMOVE = "Remove Sealed Bag"
BAG_STATUS_FULL = "Bag full"
BAG_STATUS_NO_BAG = "No Bag"
BAG_STATUS_OK = "Bag OK"

# After No Bag (128) clears to 0, wait this long then Clean if drum idle.
AUTO_CLEAN_AFTER_DRAWER_S = 60.0


def chore_error_label(chore: str | None) -> str | None:
    """Dashboard error-chip text for an open chore, else None."""
    if chore == CHORE_NEEDS_SEAL:
        return LABEL_SEAL
    if chore == CHORE_NEEDS_REMOVE:
        return LABEL_REMOVE
    return None


def chore_bag_status(chore: str | None, *, live_full: bool, live_no_bag: bool) -> str:
    """Bag status with sticky full while remove chore is open."""
    if live_full or chore in (CHORE_NEEDS_SEAL, CHORE_NEEDS_REMOVE):
        return BAG_STATUS_FULL
    if live_no_bag:
        return BAG_STATUS_NO_BAG
    return BAG_STATUS_OK


def chore_severity(chore: str | None, *, live_full: bool, live_no_bag: bool) -> str:
    if live_full or live_no_bag or chore in (CHORE_NEEDS_SEAL, CHORE_NEEDS_REMOVE):
        return "critical"
    return "ok"


def chore_active(chore: str | None) -> bool:
    return chore in (CHORE_NEEDS_SEAL, CHORE_NEEDS_REMOVE)


def merge_error_display(live_describe: str, chore: str | None) -> str:
    """Prefer chore label when sticky; else live describe_error text."""
    label = chore_error_label(chore)
    if label:
        return label
    return live_describe
