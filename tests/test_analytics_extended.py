"""Extended unit tests for analytics store, engine ranks, and metrics."""
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
    UNKNOWN_LABEL,
    compute_device_metrics,
)
from custom_components.furbulous.analytics.store import EventStore


@pytest.mark.asyncio
async def test_event_store_index_and_prune():
    hass = MagicMock()
    store = EventStore(hass, "e1")
    store._loaded = True
    store.append("visit_ended", device_id=1, payload={"duration_s": 10})
    store.append("pack", device_id=1, payload={})
    store.append("visit_ended", device_id=2, payload={"duration_s": 20})
    assert store.event_count == 3
    assert store.device_ids == {"1", "2"}
    assert len(store.events_for_device(1)) == 2
    assert len(store.events_for_device(1, event_types={"pack"})) == 1


def test_empty_metrics_none_not_fake_zero_avg():
    m = compute_device_metrics([], now=time.time())
    assert m["avg_bag_lifetime_s_30d"] is None
    assert m["avg_time_to_clear_s_30d"] is None
    assert m["avg_litter_interval_s_30d"] is None
    assert m["packs_30d"] == 0
    assert m["current_time_full_s"] == 0.0


def test_engine_empty_closes_bag_and_pack_separate():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-bag")
    eng.store._loaded = True
    eng.record_hand_mode(1, "iot", HAND_MODE_PACK)
    eng.record_hand_mode(1, "iot", HAND_MODE_EMPTY)
    # second empty debounced
    eng.record_hand_mode(1, "iot", HAND_MODE_EMPTY)
    assert len(eng.store.events_for_device(1, event_types={"pack"})) == 1
    assert len(eng.store.events_for_device(1, event_types={"empty"})) == 1
    assert len(eng.store.events_for_device(1, event_types={"bag_replaced"})) == 1


def test_engine_litter_reset_debounce():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-lit")
    eng.store._loaded = True
    eng.record_litter_reset(1, "iot")
    eng.record_litter_reset(1, "iot")  # debounced
    assert len(eng.store.events_for_device(1, event_types={"litter_reset"})) == 1


def test_engine_visit_flap_ignored():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-flap")
    eng.store._loaded = True
    box = {
        "id": 3,
        "iotid": "iot-3",
        "name": "B",
        "properties": {"workstatus": 1, "errorReportEvent": 0},
    }
    eng.process_snapshot([box])
    # leave immediately (occupy_since ~ now) → flap ignored
    box["properties"]["workstatus"] = 0
    eng.process_snapshot([box])
    assert eng.store.events_for_device(3, event_types={"visit_ended"}) == []


def test_occupying_pet_unknown_when_idle():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-occ")
    eng.store._loaded = True
    eng.process_snapshot(
        [
            {
                "id": 5,
                "iotid": "i",
                "name": "B",
                "properties": {"workstatus": 0, "errorReportEvent": 0},
            }
        ]
    )
    assert eng.occupying_pet(5) == UNKNOWN_LABEL


def test_occupying_pet_name_from_property():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-name")
    eng.store._loaded = True
    eng.process_snapshot(
        [
            {
                "id": 5,
                "iotid": "i",
                "name": "B",
                "properties": {
                    "workstatus": 1,
                    "errorReportEvent": 0,
                    "petName": "Mochi",
                },
            }
        ]
    )
    assert eng.occupying_pet(5) == "Mochi"


def test_full_recompute_flag_refreshes_without_dirty_when_idle():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-full")
    eng.store._loaded = True
    device = {
        "id": 1,
        "iotid": "i",
        "name": "B",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([device], full_recompute=True)
    eng._dirty = False
    eng.process_snapshot([device], full_recompute=True)
    assert eng.is_dirty is False


def test_diagnostics_summary_shape():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-diag")
    eng.store._loaded = True
    summary = eng.diagnostics_summary()
    assert "event_count" in summary
    assert "pet_count" in summary
    assert summary["event_count"] == 0


def test_restore_open_full_and_bag_markers():
    """After reload, open full episode + last bag/litter are restored from log."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "e-restore")
    eng.store._loaded = True
    now = time.time()
    eng.store.append(
        "bag_replaced", device_id=7, iotid="iot-7", ts=now - 86400, payload={}
    )
    eng.store.append(
        "litter_reset", device_id=7, iotid="iot-7", ts=now - 3600, payload={}
    )
    eng.store.append(
        "waste_full_on", device_id=7, iotid="iot-7", ts=now - 600, payload={}
    )
    eng._restore_device_state_from_events()
    st = eng._device_state["7"]
    assert st["last_bag_ts"] == pytest.approx(now - 86400)
    assert st["last_litter_reset_ts"] == pytest.approx(now - 3600)
    assert st["is_full"] is True
    assert st["full_episode_start"] == pytest.approx(now - 600)
    eng.recompute_all()
    m = eng.metrics_for_device(7)
    assert m["current_time_full_s"] == pytest.approx(600, abs=2)
    assert m["hours_since_bag_replaced"] == pytest.approx(24, abs=0.1)
