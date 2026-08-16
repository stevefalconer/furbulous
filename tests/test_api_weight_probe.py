"""Probe: production API surface only exposes gram weight."""
from __future__ import annotations

import pytest

from custom_components.furbulous.weight import (
    resolve_cat_weight_grams,
    source_weight_field,
)

KNOWN_PROPERTY_KEYS_FROM_CLIENT = {
    "catWeight",
    "workstatus",
    "errorReportEvent",
    "FullAutoModeSwitch",
    "childLockOnOff",
    "masterSleepOnOff",
    "catCleanOnOff",
    "handMode",
    "completionStatus",
    "excreteTimesEveryday",
    "excreteTimerEveryday",
}


def test_no_kg_or_lb_keys_in_known_client_surface():
    """Known client property set has no dedicated kg/lb weight keys."""
    lower = {k.lower() for k in KNOWN_PROPERTY_KEYS_FROM_CLIENT}
    assert "catweightkg" not in lower
    assert "catweightlb" not in lower
    assert "catweight" in lower


def test_synthetic_payload_with_only_grams():
    """Realistic device property map resolves as grams."""
    props = {k: 0 for k in KNOWN_PROPERTY_KEYS_FROM_CLIENT}
    props["catWeight"] = 5123
    assert source_weight_field(props) == "catWeight"
    assert resolve_cat_weight_grams(props) == pytest.approx(5123)
