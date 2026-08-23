"""LocalTime packing and property time helpers."""
from __future__ import annotations

import time

from custom_components.furbulous.device_time import (
    decode_local_time,
    encode_local_time,
    local_time_day_key,
    prop_time_unix,
    sane_event_ts,
)
from custom_components.furbulous.furbulous_api import FurbulousCatAPI


def test_decode_local_time_date_packing():
    """Capture values decode to the capture calendar dates."""
    # downstairs_snapshot_redacted.json — 2026-08-15
    d = decode_local_time(252189185)
    assert d is not None
    assert d.day_key == "2026-08-15"
    assert d.flag == 1
    # eco/jam captures — 2026-08-16
    d2 = decode_local_time(268966401)
    assert d2 is not None
    assert d2.day_key == "2026-08-16"
    assert encode_local_time(2026, 8, 15) == 252189185
    assert encode_local_time(2026, 8, 16) == 268966401


def test_local_time_day_rollover_detect():
    assert local_time_day_key(252189185) != local_time_day_key(268966401)
    assert local_time_day_key(None) is None
    assert decode_local_time(0xFF000000) is None  # invalid month/day


def test_prop_time_ms_to_unix():
    # seal capture workstatus_time
    assert prop_time_unix(1786937055000) == 1786937055.0
    assert prop_time_unix(1786937055) == 1786937055.0
    assert prop_time_unix(None) is None


def test_sane_event_ts_rejects_future_and_ancient():
    now = time.time()
    assert sane_event_ts(now - 60, now=now) == now - 60
    assert sane_event_ts(now + 3600, now=now) is None
    assert sane_event_ts(now - 200 * 86400, now=now) is None


def test_extract_properties_preserves_times():
    raw = {
        "workstatus": {"value": 0, "time": 1786937055000},
        "completionStatus": {"value": 1, "time": 1786927585000},
        "handMode": 3,
    }
    values, times = FurbulousCatAPI._extract_properties(raw)
    assert values["workstatus"] == 0
    assert values["completionStatus"] == 1
    assert values["handMode"] == 3
    assert times["workstatus"] == 1786937055.0
    assert times["completionStatus"] == 1786927585.0
    assert "handMode" not in times
