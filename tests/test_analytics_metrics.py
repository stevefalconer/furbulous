"""Unit tests for analytics metrics and engine edges."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from custom_components.furbulous.analytics.engine import (
    HAND_MODE_EMPTY,
    HAND_MODE_PACK,
    AnalyticsEngine,
)
from custom_components.furbulous.analytics.metrics import (
    NOT_ENOUGH_DATA,
    compute_device_metrics,
    compute_pet_metrics,
)


def test_bag_lifetime_needs_two_replaces():
    """One bag replace does not invent a lifetime."""
    now = time.time()
    events = [
        {"event_type": "bag_replaced", "ts": now - 100, "device_id": "1", "payload": {}},
    ]
    m = compute_device_metrics(events, now=now)
    assert m["last_bag_lifetime_s"] is None
    assert m["avg_bag_lifetime_s_30d"] is None
    assert m["bags_replaced_30d"] == 1


def test_bag_lifetime_and_avg():
    now = time.time()
    events = [
        {"event_type": "bag_replaced", "ts": now - 4 * 86400, "device_id": "1", "payload": {}},
        {
            "event_type": "bag_replaced",
            "ts": now - 100,
            "device_id": "1",
            "payload": {"lifetime_s": 4 * 86400},
        },
    ]
    m = compute_device_metrics(events, now=now)
    assert m["last_bag_lifetime_s"] == pytest.approx(4 * 86400)
    assert m["avg_bag_lifetime_s_30d"] == pytest.approx(4 * 86400)


def test_time_to_clear_avg_and_max():
    now = time.time()
    events = [
        {
            "event_type": "waste_full_off",
            "ts": now - 200,
            "device_id": "1",
            "payload": {"time_full_s": 1800},
        },
        {
            "event_type": "waste_full_off",
            "ts": now - 100,
            "device_id": "1",
            "payload": {"time_full_s": 7200},
        },
    ]
    m = compute_device_metrics(events, now=now)
    assert m["last_time_to_clear_s"] == 7200
    assert m["avg_time_to_clear_s_30d"] == pytest.approx(4500)
    assert m["max_time_to_clear_s_30d"] == 7200
    assert m["full_episodes_30d"] == 2


def test_current_full_waiting():
    now = time.time()
    m = compute_device_metrics(
        [],
        now=now,
        open_full_start=now - 3600,
        is_full=True,
    )
    assert m["current_time_full_s"] == pytest.approx(3600, abs=1)


def test_litter_interval():
    now = time.time()
    events = [
        {"event_type": "litter_reset", "ts": now - 19 * 86400, "device_id": "1", "payload": {}},
        {"event_type": "litter_reset", "ts": now - 100, "device_id": "1", "payload": {}},
    ]
    m = compute_device_metrics(events, now=now)
    assert m["last_litter_interval_s"] == pytest.approx(19 * 86400 - 100, abs=2)
    assert m["litter_resets_30d"] == 2


def test_favorite_box_not_enough_data():
    now = time.time()
    events = [
        {
            "event_type": "visit_ended",
            "ts": now - 10,
            "device_id": "a",
            "payload": {"pet_id": 1, "pet_name": "Mochi", "duration_s": 30},
        },
        {
            "event_type": "visit_ended",
            "ts": now - 5,
            "device_id": "a",
            "payload": {"pet_id": 1, "pet_name": "Mochi", "duration_s": 40},
        },
    ]
    m = compute_pet_metrics(events, 1, "Mochi", {"a": "Box A"}, now=now)
    assert m["favorite_box"] == NOT_ENOUGH_DATA
    assert m["visits_30d"] == 2


def test_favorite_box_picks_max():
    now = time.time()
    events = []
    for i in range(5):
        events.append(
            {
                "event_type": "visit_ended",
                "ts": now - i,
                "device_id": "a",
                "payload": {"pet_id": 1, "pet_name": "Mochi", "duration_s": 20},
            }
        )
    for i in range(2):
        events.append(
            {
                "event_type": "visit_ended",
                "ts": now - i,
                "device_id": "b",
                "payload": {"pet_id": 1, "pet_name": "Mochi", "duration_s": 20},
            }
        )
    m = compute_pet_metrics(
        events, 1, "Mochi", {"a": "Box A", "b": "Box B"}, now=now
    )
    assert m["favorite_box"] == "Box A"


@pytest.mark.asyncio
async def test_engine_visit_and_empty(monkeypatch):
    """Presence edges + empty closes bag."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-1")
    eng.store._loaded = True  # skip disk

    # Occupy
    eng.process_snapshot(
        [
            {
                "id": 42,
                "iotid": "iot-1",
                "name": "Box",
                "properties": {"workstatus": 1, "errorReportEvent": 0},
            }
        ]
    )
    assert eng._device_state["42"]["occupied"] is True

    # Leave after debounce window: fake occupy_since in the past
    eng._device_state["42"]["occupy_since"] = time.time() - 60
    eng.process_snapshot(
        [
            {
                "id": 42,
                "iotid": "iot-1",
                "name": "Box",
                "properties": {"workstatus": 0, "errorReportEvent": 0},
            }
        ]
    )
    visits = eng.store.events_for_device(42, event_types={"visit_ended"})
    assert len(visits) == 1

    eng.record_hand_mode(42, "iot-1", HAND_MODE_PACK)
    eng.record_hand_mode(42, "iot-1", HAND_MODE_EMPTY)
    packs = eng.store.events_for_device(42, event_types={"pack"})
    bags = eng.store.events_for_device(42, event_types={"bag_replaced"})
    assert len(packs) == 1
    assert len(bags) == 1

    eng.record_litter_reset(42, "iot-1")
    resets = eng.store.events_for_device(42, event_types={"litter_reset"})
    assert len(resets) == 1


@pytest.mark.asyncio
async def test_engine_full_debounce():
    """Full requires 2 consecutive polls."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-2")
    eng.store._loaded = True

    device = {
        "id": 7,
        "iotid": "iot-7",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 16},
    }
    eng.process_snapshot([device])
    assert eng._device_state["7"].get("is_full") is False
    eng.process_snapshot([device])
    assert eng._device_state["7"].get("is_full") is True
    ons = eng.store.events_for_device(7, event_types={"waste_full_on"})
    assert len(ons) == 1


def test_idle_presence_does_not_dirty_store():
    """Unchanged presence ticks must not mark analytics dirty (Pi SD)."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-idle")
    eng.store._loaded = True
    device = {
        "id": 9,
        "iotid": "iot-9",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([device], full_recompute=False)
    eng._dirty = False
    eng.process_snapshot([device], full_recompute=False)
    eng.process_snapshot([device], full_recompute=False)
    assert eng.is_dirty is False
    assert eng.store.event_count == 0
