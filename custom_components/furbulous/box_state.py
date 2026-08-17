"""Single classifier for live box properties.

The vendor API is a bag of sticky and overloaded fields. Callers must not
re-interpret ``workstatus`` / ``handMode`` / ``completionStatus`` / error bits
in three different files. This module is the only mapping from a property
snapshot to: is a cat in the box, what should HA say the box is doing, and
which faults are on.

Live 2026-08-16 (do not “fix” without a new capture):

- ``workstatus`` 0 idle, 1 clean *or* cat, 3 pack, 5 pour, 6 reset tail, 8 reset.
- ``handMode`` is last command and sticks after the globe stops.
- ``completionStatus`` 3 = clean running (2 treated the same if seen).
- ``errorReportEvent`` is a bitfield; 524288 = trash-door E4; 512 = lid off.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .entity import extract_prop_value
from .error_report import (
    is_cover_open,
    is_trash_door_blocked,
    is_waste_full,
    parse_error_code,
)

PHASE_IDLE = "idle"
PHASE_CAT = "cat_inside"
PHASE_CLEANING = "cleaning"
PHASE_RESETTING = "resetting_litter"
PHASE_POURING = "adding_litter"
PHASE_PACKING = "packing"
PHASE_TRASH_DOOR = "trash_door"
PHASE_IN_USE = "in_use"
PHASE_COMMAND = "last_command"

# Sticky last-command labels (only when workstatus is missing).
_HAND_LABELS = {
    0: "Idle",
    1: "Cleaning",
    2: "Emptying",
    3: "Packing bag",
    4: "Paused",
    5: "Resuming",
    6: "Resetting litter",
}

_CLEANING_COMPLETION = frozenset({2, 3})


def _int(raw: Any) -> int | None:
    value = extract_prop_value(raw)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class BoxState:
    """Derived live state. Cheap to rebuild every 30s poll."""

    phase: str
    label: str
    cat_present: bool
    waste_full: bool
    lid_off: bool
    trash_door: bool
    workstatus: int | None
    hand_mode: int | None
    completion: int | None
    error_code: int | None


def classify(properties: dict[str, Any] | None) -> BoxState:
    """Map a properties dict (flat or ``{value, time}``) to one BoxState."""
    props = properties or {}
    work = _int(props.get("workstatus"))
    hand = _int(props.get("handMode"))
    completion = _int(props.get("completionStatus"))
    error = parse_error_code(props.get("errorReportEvent"))
    trash = is_trash_door_blocked(props.get("errorReportEvent"))
    lid = is_cover_open(props.get("errorReportEvent"))
    full = is_waste_full(props.get("errorReportEvent"))

    phase = PHASE_IDLE
    label = "Idle"
    cat = False

    if trash:
        phase = PHASE_TRASH_DOOR
        label = "Trash door jammed"
    elif work == 8 or work == 6:
        phase = PHASE_RESETTING
        label = "Resetting litter"
    elif work == 3:
        phase = PHASE_PACKING
        label = "Packing bag"
    elif work == 5:
        phase = PHASE_POURING
        label = "Adding litter"
    elif work == 1 and completion in _CLEANING_COMPLETION:
        phase = PHASE_CLEANING
        label = "Cleaning"
    elif work == 1:
        # Vendor uses 1 for a cat *and* some cleans. Prefer "In use" over a
        # false visit; occupancy still counts this as a cat (best effort).
        phase = PHASE_CAT
        label = "In use"
        cat = True
    elif work == 0:
        phase = PHASE_IDLE
        label = "Idle"
    elif work is None and hand is not None:
        phase = PHASE_COMMAND
        label = _HAND_LABELS.get(hand, str(hand))
    elif work is not None:
        phase = PHASE_IN_USE
        label = _HAND_LABELS.get(hand, "In use") if hand is not None else "In use"

    return BoxState(
        phase=phase,
        label=label,
        cat_present=cat,
        waste_full=full,
        lid_off=lid,
        trash_door=trash,
        workstatus=work,
        hand_mode=hand,
        completion=completion,
        error_code=error,
    )
