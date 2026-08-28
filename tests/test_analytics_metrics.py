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
    assert status["label"] == "Paulie"  # red shows last cat while dirty
    assert status.get("dirty") is True
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
async def test_auto_clean_clears_dirty_via_completion_edge():
    """Auto-clean: completionStatus 3→1 clears Dirty without Clean now button."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-autoclean")
    eng.store._loaded = True
    idle = {
        "id": 22,
        "iotid": "iot-22",
        "name": "Box",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 0},
    }
    eng._device_state["22"] = {
        "occupied": False,
        "awaiting_clean_since": time.time() - 100,
        "awaiting_clean_cat": "Jet",
        "last_visitor_name": "Jet",
        "last_completion": 3,
        "last_workstatus": 1,
        "last_phase": "cleaning",
        "saw_clean_cycle": True,
        "clean_in_progress": True,
    }
    eng.process_snapshot([idle])
    assert eng.toilet_status(22)["label"] == "Idle"
    assert eng.last_clean_cat(22) == "Jet"
    assert len(eng.store.events_for_device(22, event_types={"clean"})) == 1


@pytest.mark.asyncio
async def test_seal_pack_starts_remove_chore_without_bag_age_reset():
    """Seal records pack + needs_remove; Bag age waits for No Bag clear."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-seal-bag")
    eng.store._loaded = True
    eng._device_state["31"] = {"bag_chore": "needs_seal", "is_full": True}
    eng.record_hand_mode(31, "iot-31", HAND_MODE_PACK)
    packs = eng.store.events_for_device(31, event_types={"pack"})
    bags = eng.store.events_for_device(31, event_types={"bag_replaced"})
    assert len(packs) == 1
    assert len(bags) == 0
    assert eng.bag_chore(31) == "needs_remove"


@pytest.mark.asyncio
async def test_mark_bag_replaced_service_path():
    """HA-only mark_bag_replaced sets last bag timestamp."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-mark-bag")
    eng.store._loaded = True
    eng.mark_bag_replaced(32, iotid="iot-32", source="service")
    assert len(eng.store.events_for_device(32, event_types={"bag_replaced"})) == 1
    assert eng._device_state["32"].get("last_bag_ts") is not None


@pytest.mark.asyncio
async def test_mark_bag_replaced_clears_needs_remove_when_cloud_clear():
    """mark_bag_replaced from needs_remove + clear cloud → bag_chore None."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-mark-chore")
    eng.store._loaded = True
    eng._device_state["34"] = {
        "bag_chore": "needs_remove",
        "saw_no_bag_during_remove": True,
        "remove_clean_ts_list": [1.0],
        "last_error_code": 0,
        "iotid": "iot-34",
    }
    eng.mark_bag_replaced(34, iotid="iot-34", source="service")
    assert eng.bag_chore(34) is None
    assert eng._device_state["34"].get("saw_no_bag_during_remove") is False
    assert eng._device_state["34"].get("remove_clean_ts_list") == []
    assert len(eng.store.events_for_device(34, event_types={"bag_replaced"})) == 1


@pytest.mark.asyncio
async def test_mark_bag_replaced_blocked_when_live_full_or_no_bag():
    """mark_bag_replaced with err=32 or 128 → HomeAssistantError; chore unchanged."""
    from homeassistant.exceptions import HomeAssistantError

    hass = MagicMock()
    for err, did in ((32, "35"), (128, "36")):
        eng = AnalyticsEngine(hass, f"entry-mark-gate-{did}")
        eng.store._loaded = True
        eng._device_state[did] = {
            "bag_chore": "needs_remove",
            "saw_no_bag_during_remove": True,
            "last_error_code": err,
            "iotid": f"iot-{did}",
        }
        with pytest.raises(HomeAssistantError):
            eng.mark_bag_replaced(did, iotid=f"iot-{did}", source="service")
        assert eng.bag_chore(did) == "needs_remove"
        assert eng._device_state[did].get("saw_no_bag_during_remove") is True
        assert len(eng.store.events_for_device(did, event_types={"bag_replaced"})) == 0


@pytest.mark.asyncio
async def test_empty_clears_needs_remove_while_live_full():
    """Empty with needs_remove + err=32 clears chore; exactly one bag_replaced."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-empty-chore")
    eng.store._loaded = True
    eng._device_state["37"] = {
        "bag_chore": "needs_remove",
        "saw_no_bag_during_remove": False,
        "last_error_code": 32,
        "is_full": True,
        "full_episode_start": time.time() - 600,
        "iotid": "iot-37",
    }
    eng.record_hand_mode(37, "iot-37", HAND_MODE_EMPTY)
    assert eng.bag_chore(37) is None
    assert eng._device_state["37"].get("saw_no_bag_during_remove") is False
    bags = eng.store.events_for_device(37, event_types={"bag_replaced"})
    assert len(bags) == 1


@pytest.mark.asyncio
async def test_mark_bag_replaced_hours_ago():
    """hours_ago backdates Bag age."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-mark-bag-ago")
    eng.store._loaded = True
    eng.mark_bag_replaced(33, iotid="iot-33", source="service", hours_ago=3.0)
    eng.recompute_all()
    assert eng.metrics_for_device(33)["hours_since_bag_replaced"] == pytest.approx(
        3.0, abs=0.05
    )


@pytest.mark.asyncio
async def test_awaiting_clears_when_idle_after_saw_clean():
    """If we saw a clean cycle, Idle+Complete clears awaiting without waiting 30m."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-idle-clean")
    eng.store._loaded = True
    idle = {
        "id": 34,
        "iotid": "iot-34",
        "name": "Box",
        "properties": {
            "workstatus": 0,
            "completionStatus": 1,
            "errorReportEvent": 0,
        },
    }
    eng._device_state["34"] = {
        "occupied": False,
        "awaiting_clean_since": time.time() - 120,
        "awaiting_clean_cat": "Vinnie",
        "last_visitor_name": "Vinnie",
        "saw_clean_cycle": True,
        "clean_in_progress": True,
        "last_completion": 3,
        "last_workstatus": 1,
        "last_phase": "cleaning",
    }
    eng.process_snapshot([idle])
    assert eng.toilet_status(34)["label"] == "Idle"
    assert eng._device_state["34"].get("awaiting_clean_since") is None


@pytest.mark.asyncio
async def test_wc_prefer_cloud_start_time_for_last_visit():
    """WC start_time drives Last visit even if presence stamped a later wall time."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-wc-prefer")
    eng.store._loaded = True
    eng.pets = [
        {
            "id": 1,
            "name": "Jet",
            "weight": 17,
            "unit": 1,
        }
    ]
    eng._device_state["40"] = {
        "last_visit_ts": time.time(),  # HA wall clock (too late)
        "last_visitor_name": "Jet",
    }
    device = {
        "id": 40,
        "iotid": "iot-40",
        "properties": {"LocalTime": 268966401},
        "wc_history": [
            {"start_time": 1786851449, "weight": 7882, "minute": 0, "second": 45}
        ],
    }
    eng.ingest_wc_history(device)
    assert eng._device_state["40"]["last_visit_ts"] == 1786851449.0
    # Second ingest still prefers WC start_time over a later HA wall stamp
    eng._device_state["40"]["last_visit_ts"] = time.time()
    eng.ingest_wc_history(device)
    assert eng._device_state["40"]["last_visit_ts"] == 1786851449.0


@pytest.mark.asyncio
async def test_wc_day_rollover_resets_watermark():
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-wc-day")
    eng.store._loaded = True
    eng._device_state["41"] = {
        "local_time_day_key": "2026-08-15",
        "wc_ingested_through": 1786851449.0,
    }
    device = {
        "id": 41,
        "iotid": "iot-41",
        "properties": {"LocalTime": 268966401},  # 2026-08-16
    }
    assert eng._update_local_day_key(device) is True
    assert eng._device_state["41"]["local_time_day_key"] == "2026-08-16"
    assert eng._device_state["41"]["wc_ingested_through"] == 0.0


@pytest.mark.asyncio
async def test_last_clean_from_completion_status_time():
    """Clean finish uses cloud completionStatus time when present."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-clean-cloud-ts")
    eng.store._loaded = True
    cloud_ts = time.time() - 600
    idle = {
        "id": 42,
        "iotid": "iot-42",
        "name": "Box",
        "properties": {
            "workstatus": 0,
            "completionStatus": 1,
            "errorReportEvent": 0,
        },
        "property_times": {"completionStatus": cloud_ts, "workstatus": cloud_ts},
    }
    eng._device_state["42"] = {
        "occupied": False,
        "awaiting_clean_since": time.time() - 120,
        "awaiting_clean_cat": "Vinnie",
        "last_visitor_name": "Vinnie",
        "saw_clean_cycle": True,
        "clean_in_progress": True,
        "last_completion": 3,
        "last_workstatus": 1,
        "last_phase": "cleaning",
    }
    eng.process_snapshot([idle])
    assert eng.last_clean_ts(42) == pytest.approx(cloud_ts, abs=1.0)


@pytest.mark.asyncio
async def test_full_clear_without_remove_stays_needs_remove_chore():
    """Full bit clearing (e.g. after seal) sticks remove chore — no bag age yet."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-bag-raw")
    eng.store._loaded = True
    full = {
        "id": 23,
        "iotid": "iot-23",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 32},
    }
    clear = {
        "id": 23,
        "iotid": "iot-23",
        "name": "Box",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([full])
    eng.process_snapshot([full])
    eng.process_snapshot([clear])
    assert eng.bag_chore(23) == "needs_remove"
    bags = eng.store.events_for_device(23, event_types={"bag_replaced"})
    assert bags == []


@pytest.mark.asyncio
async def test_reconcile_clears_stuck_dirty_when_idle_healthy():
    """After Dirty threshold, healthy Idle box is marked cleaned (missed auto-clean)."""
    from custom_components.furbulous.analytics.engine import DIRTY_AFTER_S

    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-reconcile")
    eng.store._loaded = True
    eng._device_state["25"] = {
        "occupied": False,
        "awaiting_clean_since": time.time() - DIRTY_AFTER_S - 60,
        "awaiting_clean_cat": "Vinnie",
        "last_visitor_name": "Vinnie",
        "last_phase": "idle",
        "last_completion": 1,
        "last_workstatus": 0,
        "dirty_notified": True,
    }
    idle = {
        "id": 25,
        "iotid": "iot-25",
        "name": "Master",
        "properties": {
            "workstatus": 0,
            "completionStatus": 1,
            "errorReportEvent": 0,
            "handMode": 1,
        },
    }
    eng.process_snapshot([idle])
    assert eng.toilet_status(25)["label"] == "Idle"
    assert eng.needs_cleaning(25) is False
    assert len(eng.store.events_for_device(25, event_types={"clean"})) == 1


@pytest.mark.asyncio
async def test_bag_age_resets_when_no_bag_bit_clears():
    """Live Downstairs: No Bag (128) → 0 after new bag also restarts Bag age."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-nobag-clear")
    eng.store._loaded = True
    no_bag = {
        "id": 24,
        "iotid": "iot-24",
        "name": "Downstairs",
        "properties": {"workstatus": 0, "errorReportEvent": 128},
    }
    clear = {
        "id": 24,
        "iotid": "iot-24",
        "name": "Downstairs",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([no_bag])
    eng.process_snapshot([clear])
    bags = eng.store.events_for_device(24, event_types={"bag_replaced"})
    assert len(bags) == 1
    assert bags[0].get("source") == "presence_no_bag_cleared"
    eng.cancel_pending_auto_cleans()


@pytest.mark.asyncio
async def test_engine_full_clear_after_confirm_is_sealed_awaiting_remove():
    """Confirmed full → clear (typical post-seal) waits for No Bag clear for bag age."""
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
    assert offs[0]["payload"].get("cleared_how") == "sealed_awaiting_remove"
    assert bags == []
    assert eng.bag_chore(11) == "needs_remove"


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


@pytest.mark.asyncio
async def test_a1_clean_without_awaiting_stamps_last_cleaned():
    """A1: Clean finish records Last cleaned even when not Dirty/awaiting."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-a1-clean")
    eng.store._loaded = True
    cloud_ts = time.time() - 30
    # Saw clean running (no prior visit / awaiting)
    cleaning = {
        "id": 50,
        "iotid": "iot-50",
        "name": "Box",
        "properties": {
            "workstatus": 1,
            "completionStatus": 3,
            "errorReportEvent": 0,
        },
    }
    eng.process_snapshot([cleaning])
    assert eng._device_state["50"].get("saw_clean_cycle") is True
    assert eng._device_state["50"].get("awaiting_clean_since") is None
    idle = {
        "id": 50,
        "iotid": "iot-50",
        "name": "Box",
        "properties": {
            "workstatus": 0,
            "completionStatus": 1,
            "errorReportEvent": 0,
        },
        "property_times": {"workstatus": cloud_ts, "completionStatus": cloud_ts},
    }
    eng.process_snapshot([idle])
    assert eng.last_clean_ts(50) == pytest.approx(cloud_ts, abs=1.0)
    assert len(eng.store.events_for_device(50, event_types={"clean"})) == 1
    assert eng.toilet_status(50)["label"] == "Idle"


@pytest.mark.asyncio
async def test_a2_cloud_ts_prefers_edged_key_and_skew():
    """A2: edged property first; reconcile skew rejects ancient sticky times."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-a2-skew")
    eng.store._loaded = True
    now = time.time()
    stale = now - 10_000
    fresh = now - 20
    device = {
        "property_times": {
            "completionStatus": stale,
            "workstatus": fresh,
        }
    }
    # Prefer workstatus when listed first
    assert eng._cloud_event_ts(
        device, "workstatus", "completionStatus", now=now
    ) == pytest.approx(fresh, abs=0.5)
    # Skew drops stale primary → falls through to fresh secondary
    assert eng._cloud_event_ts(
        device,
        "completionStatus",
        "workstatus",
        now=now,
        max_skew_s=3600.0,
    ) == pytest.approx(fresh, abs=0.5)
    # Both too old → wall clock
    wall = eng._cloud_event_ts(
        device,
        "completionStatus",
        now=now,
        max_skew_s=60.0,
    )
    assert wall == pytest.approx(now, abs=2.0)


@pytest.mark.asyncio
async def test_a3_litter_reset_uses_workstatus_property_time():
    """A3: device workstatus=8 stamps litter age from cloud property time."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-a3-litter")
    eng.store._loaded = True
    cloud_ts = time.time() - 45
    idle = {
        "id": 51,
        "iotid": "iot-51",
        "properties": {"workstatus": 0, "errorReportEvent": 0},
    }
    eng.process_snapshot([idle])
    resetting = {
        "id": 51,
        "iotid": "iot-51",
        "properties": {"workstatus": 8, "errorReportEvent": 0},
        "property_times": {"workstatus": cloud_ts},
    }
    eng.process_snapshot([resetting])
    resets = eng.store.events_for_device(51, event_types={"litter_reset"})
    assert len(resets) == 1
    assert resets[0]["ts"] == pytest.approx(cloud_ts, abs=1.0)


@pytest.mark.asyncio
async def test_b1_cloud_pack_records_pack_without_bag_replaced():
    """Pack finish records pack; bag_replaced waits for No Bag clear."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-b1-pack")
    eng.store._loaded = True
    cloud_ts = time.time() - 15
    idle = {
        "id": 52,
        "iotid": "iot-52",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 0},
    }
    eng.process_snapshot([idle])
    packing = {
        "id": 52,
        "iotid": "iot-52",
        "properties": {"workstatus": 3, "completionStatus": 1, "errorReportEvent": 0},
    }
    eng.process_snapshot([packing])
    assert eng._device_state["52"].get("pack_in_progress") is True
    done = {
        "id": 52,
        "iotid": "iot-52",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 0},
        "property_times": {"workstatus": cloud_ts},
    }
    eng.process_snapshot([done])
    packs = eng.store.events_for_device(52, event_types={"pack"})
    bags = eng.store.events_for_device(52, event_types={"bag_replaced"})
    assert len(packs) == 1
    assert packs[0]["source"] == "presence_pack"
    assert bags == []
    eng.process_snapshot([done])
    assert len(eng.store.events_for_device(52, event_types={"pack"})) == 1


@pytest.mark.asyncio
async def test_b2_wc_dedup_skips_presence_overlap():
    """B2: WC row matching an existing presence leave is not double-counted."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-b2-dedup")
    eng.store._loaded = True
    eng.pets = [{"id": 1, "name": "Jet", "weight": 17, "unit": 1}]
    # Use recent ts — store prunes events older than 90 days.
    start = time.time() - 600.0
    leave = start + 45.0
    eng.store.append(
        "visit_ended",
        device_id="53",
        iotid="iot-53",
        source="presence",
        payload={"duration_s": 45.0, "weight_g": 7882.0, "pet_name": "Jet"},
        ts=leave,
    )
    # Force watermark low so WC would otherwise append
    eng._device_state["53"] = {"wc_ingested_through": 0.0}
    device = {
        "id": 53,
        "iotid": "iot-53",
        "properties": {},
        "wc_history": [
            {"start_time": start, "weight": 7882, "minute": 0, "second": 45}
        ],
    }
    eng.ingest_wc_history(device)
    visits = eng.store.events_for_device(53, event_types={"visit_ended"})
    assert len(visits) == 1
    assert visits[0]["source"] == "presence"
    # Last visit display still prefers WC start
    assert eng._device_state["53"]["last_visit_ts"] == start


@pytest.mark.asyncio
async def test_a2_bag_clear_does_not_use_sticky_handmode_time():
    """A2: bag age on full-clear prefers errorReportEvent, not sticky handMode."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-a2-bag")
    eng.store._loaded = True
    now = time.time()
    err_ts = now - 10
    sticky_hand = now - 5000
    full = {
        "id": 54,
        "iotid": "iot-54",
        "properties": {"workstatus": 0, "errorReportEvent": 32},
    }
    eng._device_state["54"] = {
        "occupied": False,
        "last_error_code": 32,
        "is_full": True,
        "full_episode_start": now - 600,
        "full_true_polls": 2,
        "last_workstatus": 0,
        "last_completion": 1,
        "last_phase": "idle",
    }
    cleared = {
        "id": 54,
        "iotid": "iot-54",
        "properties": {"workstatus": 0, "errorReportEvent": 0, "handMode": 1},
        "property_times": {
            "errorReportEvent": err_ts,
            "handMode": sticky_hand,
            "workstatus": now - 100,
        },
    }
    eng.process_snapshot([cleared])
    bags = eng.store.events_for_device(54, event_types={"bag_replaced"})
    assert len(bags) == 1
    assert bags[0]["ts"] == pytest.approx(err_ts, abs=1.0)


@pytest.mark.asyncio
async def test_bag_chore_sticky_remove_after_seal_clears_full():
    """Cleo path: full(32) → pack → err 0 stays needs_remove / Bag full labels."""
    from custom_components.furbulous.bag_chore import (
        LABEL_REMOVE,
        LABEL_SEAL,
        chore_bag_status,
        merge_error_display,
    )
    from custom_components.furbulous.error_report import describe_error

    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-chore")
    eng.store._loaded = True
    # Confirm full
    full = {
        "id": 88,
        "iotid": "iot-88",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 32},
    }
    eng.process_snapshot([full])
    eng.process_snapshot([full])  # FULL_CONFIRM_POLLS=2
    assert eng.bag_chore(88) == "needs_seal"
    assert describe_error(32) == LABEL_SEAL
    assert merge_error_display(describe_error(32), eng.bag_chore(88)) == LABEL_SEAL
    assert chore_bag_status(eng.bag_chore(88), live_full=True, live_no_bag=False) == (
        "Bag full"
    )

    packing = {
        "id": 88,
        "iotid": "iot-88",
        "properties": {"workstatus": 3, "completionStatus": 1, "errorReportEvent": 32},
    }
    eng.process_snapshot([packing])
    sealed = {
        "id": 88,
        "iotid": "iot-88",
        "properties": {"workstatus": 0, "completionStatus": 3, "errorReportEvent": 0},
    }
    eng.process_snapshot([sealed])
    assert eng.bag_chore(88) == "needs_remove"
    assert merge_error_display("No error", eng.bag_chore(88)) == LABEL_REMOVE
    assert chore_bag_status(eng.bag_chore(88), live_full=False, live_no_bag=False) == (
        "Bag full"
    )
    # Seal must not reset bag age yet
    assert eng.store.events_for_device(88, event_types={"bag_replaced"}) == []

    no_bag = {
        "id": 88,
        "iotid": "iot-88",
        "properties": {"workstatus": 0, "completionStatus": 3, "errorReportEvent": 128},
    }
    eng.process_snapshot([no_bag])
    assert eng.bag_chore(88) == "needs_remove"
    assert eng._device_state["88"].get("saw_no_bag_during_remove") is True

    cleared = {
        "id": 88,
        "iotid": "iot-88",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 0},
    }
    eng.process_snapshot([cleared])
    assert eng.bag_chore(88) is None
    bags = eng.store.events_for_device(88, event_types={"bag_replaced"})
    assert len(bags) == 1
    assert bags[0]["source"] == "presence_no_bag_cleared"
    eng.cancel_pending_auto_cleans()


@pytest.mark.asyncio
async def test_auto_clean_armed_after_no_bag_clear():
    """128→0 arms auto-clean timer (token + timestamp)."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-autoclean-arm")
    eng.store._loaded = True
    no_bag = {
        "id": 89,
        "iotid": "iot-89",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 128},
    }
    cleared = {
        "id": 89,
        "iotid": "iot-89",
        "properties": {"workstatus": 0, "completionStatus": 1, "errorReportEvent": 0},
    }
    eng.process_snapshot([no_bag])
    eng._device_state["89"]["bag_chore"] = "needs_remove"
    eng.process_snapshot([cleared])
    assert eng._device_state["89"].get("auto_clean_armed_ts") is not None
    assert eng._device_state["89"].get("auto_clean_token") is not None
    eng.cancel_pending_auto_cleans()



@pytest.mark.asyncio
async def test_cat_leave_does_not_stamp_last_cleaned():
    """workstatus 1→0 on visit end is not a barrel clean (Jet Downstairs 2026-08-25)."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-cat-leave")
    eng.store._loaded = True
    cat = {
        "id": 77,
        "iotid": "iot-77",
        "properties": {
            "workstatus": 1,
            "completionStatus": 1,
            "errorReportEvent": 0,
            "catWeight": 8167,
        },
    }
    eng.process_snapshot([cat])
    eng._device_state["77"]["occupied"] = True
    eng._device_state["77"]["occupy_since"] = time.time() - 90
    eng._device_state["77"]["last_workstatus"] = 1
    leave = {
        "id": 77,
        "iotid": "iot-77",
        "properties": {
            "workstatus": 0,
            "completionStatus": 1,
            "errorReportEvent": 0,
            "catWeight": 8167,
        },
    }
    eng.process_snapshot([leave])
    assert eng.store.events_for_device(77, event_types={"clean"}) == []
    assert eng._device_state["77"].get("awaiting_clean_since") is not None
    assert eng.toilet_status(77)["severity"] in ("attention", "critical")
