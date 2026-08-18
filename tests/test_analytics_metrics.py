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
    EMPTY_LABEL,
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
    assert m["favorite_box"] == EMPTY_LABEL
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


@pytest.mark.asyncio
async def test_engine_full_accepts_32():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-32")
    eng.store._loaded = True
    device = {
        "id": 8,
        "iotid": "iot-8",
        "name": "Upstairs",
        "properties": {"workstatus": 0, "errorReportEvent": 32},
    }
    eng.process_snapshot([device])
    eng.process_snapshot([device])
    assert eng._device_state["8"].get("is_full") is True


@pytest.mark.asyncio
async def test_toilet_status_idle_dirty_and_clean():
    """Visit → awaiting (attention) → Dirty after 30m → Idle after barrel clean."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-toilet")
    eng.store._loaded = True
    # Occupy then leave (visit)
    in_box = {
        "id": 21,
        "iotid": "iot-21",
        "name": "Box",
        "properties": {
            "workstatus": 1,
            "completionStatus": 1,
            "errorReportEvent": 0,
            "catWeight": 5000,
        },
    }
    idle = {
        "id": 21,
        "iotid": "iot-21",
        "name": "Box",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 0},
    }
    eng.process_snapshot([in_box])
    eng._device_state["21"]["occupy_since"] = time.time() - 60
    eng._device_state["21"]["last_pet_name"] = "Paulie"
    eng.process_snapshot([idle])
    status = eng.toilet_status(21)
    assert status["severity"] == "attention"
    assert status["label"] == "Paulie"
    assert eng.needs_cleaning(21) is False

    eng._device_state["21"]["awaiting_clean_since"] = time.time() - 2000
    status = eng.toilet_status(21)
    assert status["severity"] == "critical"
    assert status["label"] == "Dirty"
    assert eng.needs_cleaning(21) is True

    cleaning = {
        "id": 21,
        "iotid": "iot-21",
        "name": "Box",
        "properties": {
            "workstatus": 1,
            "completionStatus": 3,
            "errorReportEvent": 0,
        },
    }
    eng.process_snapshot([cleaning])
    assert eng._device_state["21"].get("clean_in_progress") is True
    eng.process_snapshot([idle])
    assert eng.toilet_status(21)["label"] == "Idle"
    assert eng.needs_cleaning(21) is False
    assert eng.last_clean_cat(21) == "Paulie"
    assert eng.last_clean_ts(21) is not None
    cleans = eng.store.events_for_device(21, event_types={"clean"})
    assert len(cleans) == 1


@pytest.mark.asyncio
async def test_engine_full_clear_restarts_bag_age():
    """When bag-full error clears in the cloud, Bag age restarts (bag_replaced)."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-bag-clear")
    eng.store._loaded = True
    full = {
        "id": 11,
        "iotid": "iot-11",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 32},
    }
    clear = {
        "id": 11,
        "iotid": "iot-11",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([full])
    eng.process_snapshot([full])
    assert eng._device_state["11"].get("is_full") is True
    eng.process_snapshot([clear])
    assert eng._device_state["11"].get("is_full") is False
    offs = eng.store.events_for_device(11, event_types={"waste_full_off"})
    bags = eng.store.events_for_device(11, event_types={"bag_replaced"})
    assert len(offs) == 1
    assert offs[0]["payload"].get("cleared_how") == "error_cleared"
    assert len(bags) == 1
    eng.recompute_all()
    assert eng.metrics_for_device(11)["hours_since_bag_replaced"] == pytest.approx(
        0.0, abs=0.05
    )


@pytest.mark.asyncio
async def test_engine_clean_and_e4_are_not_visits():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-clean")
    eng.store._loaded = True
    eng.process_snapshot(
        [
            {
                "id": 9,
                "iotid": "iot-9",
                "name": "Box",
                "properties": {
                    "workstatus": 1,
                    "completionStatus": 3,
                    "errorReportEvent": 0,
                },
            }
        ]
    )
    assert eng._device_state["9"]["occupied"] is False
    eng.process_snapshot(
        [
            {
                "id": 9,
                "iotid": "iot-9",
                "name": "Box",
                "properties": {
                    "workstatus": 1,
                    "completionStatus": 5,
                    "errorReportEvent": 64 | 524288,
                },
            }
        ]
    )
    assert eng._device_state["9"]["occupied"] is False
    assert eng.store.events_for_device(9, event_types={"visit_started"}) == []


def test_full_recompute_does_not_open_a_visit():
    """5 min snapshot must not invent occupancy (stale vs presence)."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-full-occ")
    eng.store._loaded = True
    eng.process_snapshot(
        [
            {
                "id": 11,
                "iotid": "iot-11",
                "name": "Box",
                "properties": {"workstatus": 1, "errorReportEvent": 0},
            }
        ],
        full_recompute=True,
    )
    assert "11" not in eng._device_state or eng._device_state.get("11", {}).get(
        "occupied"
    ) in (None, False)
    assert eng.store.events_for_device(11, event_types={"visit_started"}) == []


@pytest.mark.asyncio
async def test_engine_workstatus_8_records_device_litter_reset():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-ws8")
    eng.store._loaded = True
    idle = {
        "id": 10,
        "iotid": "iot-10",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([idle])
    resetting = {
        "id": 10,
        "iotid": "iot-10",
        "name": "Box",
        "properties": {"workstatus": 8, "errorReportEvent": 0},
    }
    eng.process_snapshot([resetting])
    resets = eng.store.events_for_device(10, event_types={"litter_reset"})
    assert len(resets) == 1
    assert resets[0]["source"] == "device"


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
