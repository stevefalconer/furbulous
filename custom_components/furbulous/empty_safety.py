"""Shared Empty-button arming state (confirm drum closed before dump)."""
from __future__ import annotations

import time

# device_id (str) -> unix expiry
_armed_until: dict[str, float] = {}

ARM_SECONDS = 90.0


def arm_empty(device_id: str | int) -> None:
    """Arm Empty for ARM_SECONDS."""
    _armed_until[str(device_id)] = time.time() + ARM_SECONDS


def disarm_empty(device_id: str | int) -> None:
    """Clear Empty arm."""
    _armed_until.pop(str(device_id), None)


def is_empty_armed(device_id: str | int) -> bool:
    """True if Empty is currently armed."""
    exp = _armed_until.get(str(device_id), 0.0)
    return time.time() < exp


def consume_empty_arm(device_id: str | int) -> bool:
    """If armed, disarm and return True; else False."""
    if is_empty_armed(device_id):
        disarm_empty(device_id)
        return True
    return False
