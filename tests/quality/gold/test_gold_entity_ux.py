"""Gold: HA entity UX (categories, names, disabled defaults, OK semantics)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.furbulous.binary_sensor import (
    FurbulousCoverOpenSensor,
    FurbulousDrawerNotInPlaceSensor,
    FurbulousSleepModeSensor,
    FurbulousWasteBinFullSensor,
)
from custom_components.furbulous.device_entities import (
    binary_sensor_entities_for_device,
    button_entities_for_device,
    sensor_entities_for_device,
    switch_entities_for_device,
)
from datetime import time

from custom_components.furbulous.live_extra_sensors import (
    FurbulousCompletionStatusSensor,
    FurbulousHandModeSensor,
)
from custom_components.furbulous.schedule_props import (
    _format_time_value,
    encode_time,
    first_prop,
    raw_to_time,
    resolve_write_payload,
)
from custom_components.furbulous.time import schedule_time_entities


_DEFAULT_PROPS = {
    "handMode": 1,
    "completionStatus": 1,
    "masterSleepOnOff": 0,
    "DisplaySwitch": 1,
    "errorReportEvent": 0,
    "displayStartTime": 1380,  # 23:00
    "displayEndTime": 420,  # 07:00
    "sleepTimeStart": 720,  # 12:00
    "sleepTimeStop": 360,  # 06:00
}


def _coord(props=None, stats=None):
    c = MagicMock()
    # Use explicit None check so props={} means empty properties (not defaults).
    use_props = _DEFAULT_PROPS if props is None else props
    c.data = {
        "devices": [
            {
                "id": 1,
                "iotid": "iot-1",
                "name": "Box",
                "version": "1.0",
                "properties": use_props,
                "daily_stats": stats or {"times": 2, "avg_duration": 30},
                "device_online": 1,
                "is_disturb": 0,
                "active_time": 1_700_000_000,
            }
        ],
        "pets": [],
    }
    c.last_update_success = True
    return c


def _analytics():
    a = MagicMock()
    a.metrics_for_device.return_value = {
        "visits_30d": 10,
        "visits_7d": 3,
        "packs_30d": 1,
    }
    a.occupying_pet.return_value = "-"
    a.last_visitor.return_value = "Mochi"
    a.last_visit_ts.return_value = 1_700_000_100.0
    a.last_visit_weight_g.return_value = 4200.0
    a.async_add_listener = MagicMock(return_value=lambda: None)
    a._device_state = {
        "1": {
            "last_visitor_name": "Mochi",
            "last_visit_ts": 1_700_000_100.0,
            "last_match_method": "closest_weight",
            "last_match_confidence": "high",
        }
    }
    return a


def test_config_entity_categories():
    switches = switch_entities_for_device(_coord(), MagicMock(), _coord().data["devices"][0])
    by_key = {s.translation_key: s for s in switches}
    for key in ("full_auto_mode", "do_not_disturb", "child_lock"):
        cat = by_key[key].entity_category
        assert cat is not None and "config" in str(cat).lower()
    assert by_key["empty_confirm_ready"].entity_category is None
    assert "screen_off" not in by_key  # replaced by Screen mode select


def test_empty_names_sort_together():
    strings = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "custom_components"
            / "furbulous"
            / "strings.json"
        ).read_text()
    )
    empty_btn = strings["entity"]["button"]["empty"]["name"]
    empty_sw = strings["entity"]["switch"]["empty_confirm_ready"]["name"]
    assert empty_btn.startswith("Empty")
    assert empty_sw.startswith("Empty")


def test_period_average_name_prefixes():
    """Cat-parent grouping: Visits / Bag / Litter word prefixes (not bare 7d)."""
    strings = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "custom_components"
            / "furbulous"
            / "strings.json"
        ).read_text()
    )
    sensors = strings["entity"]["sensor"]
    for key, expected_prefix in (
        ("visits_7_days", "Visits"),
        ("visits_30_days", "Visits"),
        ("avg_visit_duration_30d", "Visit"),
        ("avg_bag_lifetime_30d", "Bag"),
        ("avg_litter_interval_30d", "Litter"),
        ("packs_30d", "Bag"),
        ("pet_visits_7d", "Visits"),
        ("pet_visits_30d", "Visits"),
        ("hours_since_bag_replaced", "Bag"),
        ("hours_since_litter_reset", "Litter"),
    ):
        name = sensors[key]["name"]
        assert name.startswith(expected_prefix), f"{key}={name}"


def test_problem_status_ok_semantics():
    coord = _coord({"errorReportEvent": 0})
    waste = FurbulousWasteBinFullSensor(coord, 1)
    cover = FurbulousCoverOpenSensor(coord, 1)
    drawer = FurbulousDrawerNotInPlaceSensor(coord, 1)
    assert waste.is_on is False
    assert cover.is_on is False
    assert drawer.is_on is False
    assert "when_ok" in waste.extra_state_attributes
    assert waste.translation_key == "waste_bin_status"
    assert cover.translation_key == "cover_status"
    assert drawer.translation_key == "drawer_status"

    coord_full = _coord({"errorReportEvent": 16})
    assert FurbulousWasteBinFullSensor(coord_full, 1).is_on is True
    # Live Upstairs (2026-08-16): full bag reports 32, not 16
    coord_full_32 = _coord({"errorReportEvent": 32})
    assert FurbulousWasteBinFullSensor(coord_full_32, 1).is_on is True
    # Bit 128 = No Bag (not lid). Cover/lid PROBLEM sensor is bit 512 only.
    coord_no_bag = _coord({"errorReportEvent": 128})
    assert FurbulousCoverOpenSensor(coord_no_bag, 1).is_on is False
    from custom_components.furbulous.binary_sensor import FurbulousNoBagSensor

    assert FurbulousNoBagSensor(coord_no_bag, 1).is_on is True
    coord_lid = _coord({"errorReportEvent": 512})
    assert FurbulousCoverOpenSensor(coord_lid, 1).is_on is True
    # Drawer-out is not a cloud bit; 64 is not drawer (E4 uses 64|524288)
    coord_dr = _coord({"errorReportEvent": 64})
    assert FurbulousDrawerNotInPlaceSensor(coord_dr, 1).is_on is False
    coord_e4 = _coord({"errorReportEvent": 64 | 524288})
    assert FurbulousDrawerNotInPlaceSensor(coord_e4, 1).is_on is False
    from custom_components.furbulous.binary_sensor import FurbulousTrashDoorSensor

    assert FurbulousTrashDoorSensor(coord_e4, 1).is_on is True
    assert FurbulousTrashDoorSensor(_coord({"errorReportEvent": 0}), 1).is_on is False
    coord_combo = _coord({"errorReportEvent": 32 | 64})
    assert FurbulousWasteBinFullSensor(coord_combo, 1).is_on is True
    assert FurbulousDrawerNotInPlaceSensor(coord_combo, 1).is_on is False


def test_box_action_labels():
    for code, label in (
        (0, "Idle"),
        (1, "Cleaning"),
        (2, "Emptying"),
        (3, "Packing bag"),
        (4, "Paused"),
        (5, "Resuming"),
        (6, "Resetting litter"),
    ):
        s = FurbulousHandModeSensor(_coord({"handMode": code}), 1)
        assert s.native_value == label
    assert FurbulousHandModeSensor(_coord({"handMode": 1}), 1).translation_key == "box_action"
    idle_sticky = FurbulousHandModeSensor(
        _coord({"handMode": 1, "workstatus": 0}), 1
    )
    assert idle_sticky.native_value == "Idle"
    cleaning = FurbulousHandModeSensor(
        _coord({"handMode": 1, "workstatus": 1, "completionStatus": 3}), 1
    )
    assert cleaning.native_value == "Cleaning"


def test_box_action_and_cycle_status_use_presence_coordinator():
    """Live cycle state belongs on the 30s properties poll, not the 5 min snapshot."""
    full = _coord({"handMode": 0, "completionStatus": 1})
    presence = _coord({"handMode": 1, "completionStatus": 2})
    entities = sensor_entities_for_device(
        full, presence, _analytics(), full.data["devices"][0]
    )
    hand = next(e for e in entities if e.translation_key == "box_action")
    cycle = next(e for e in entities if e.translation_key == "cycle_completion")
    assert hand.coordinator is presence
    assert cycle.coordinator is presence
    assert hand.native_value == "Cleaning"
    assert cycle.native_value == "In progress"


def test_safety_sensors_use_presence_coordinator():
    full = _coord({"errorReportEvent": 0, "DisplaySwitch": 0})
    presence = _coord(
        {"errorReportEvent": 32, "DisplaySwitch": 1, "displayStartTime": 0, "displayEndTime": 0}
    )
    bins = binary_sensor_entities_for_device(
        full, presence, full.data["devices"][0]
    )
    waste = next(e for e in bins if e.translation_key == "waste_bin_status")
    cover = next(e for e in bins if e.translation_key == "cover_status")
    screen = next(e for e in bins if e.translation_key == "energy_saving_active")
    assert waste.coordinator is presence
    assert cover.coordinator is presence
    assert screen.coordinator is presence
    sensors = sensor_entities_for_device(
        full, presence, _analytics(), full.data["devices"][0]
    )
    err = next(e for e in sensors if e.translation_key == "error")
    assert err.coordinator is presence


def test_screen_mode_options_are_translation_keys():
    from custom_components.furbulous.select import (
        SCREEN_MODE_ALWAYS_ON,
        SCREEN_MODE_OPTIONS,
        SCREEN_MODE_SCHEDULED,
        FurbulousScreenModeSelect,
    )

    assert SCREEN_MODE_OPTIONS == ["always_on", "scheduled"]
    sel = FurbulousScreenModeSelect(_coord({"DisplaySwitch": 0}), MagicMock(), 1, "iot-1")
    assert sel.current_option == SCREEN_MODE_ALWAYS_ON
    assert sel.options == SCREEN_MODE_OPTIONS
    sel.coordinator.data["devices"][0]["properties"]["DisplaySwitch"] = 1
    assert sel.current_option == SCREEN_MODE_SCHEDULED


def test_cycle_completion_mapping():
    s = FurbulousCompletionStatusSensor(_coord({"completionStatus": 1}), 1)
    assert s.native_value == "Complete"
    assert s.extra_state_attributes["raw_completion_status"] == 1
    assert FurbulousCompletionStatusSensor(_coord({}), 1).native_value == "-"
    assert (
        FurbulousCompletionStatusSensor(_coord({"completionStatus": 5}), 1).native_value
        == "Litter reset done"
    )


def test_screen_off_and_quiet_hours_time_entities_writable():
    coord = _coord()
    api = MagicMock()
    entities = schedule_time_entities(coord, api, 1, "iot-1")
    by_key = {e.translation_key: e for e in entities}
    assert set(by_key) == {
        "screen_schedule_start",
        "screen_schedule_end",
        "quiet_hours_start",
        "quiet_hours_end",
    }
    assert by_key["screen_schedule_start"].native_value == time(23, 0)
    assert by_key["screen_schedule_end"].native_value == time(7, 0)
    assert by_key["quiet_hours_start"].native_value == time(12, 0)
    assert "config" in str(by_key["screen_schedule_start"].entity_category).lower()
    empty = schedule_time_entities(_coord({}), api, 1, "iot-1")
    assert empty[0].native_value == time(23, 0)


def test_format_time_value_variants():
    assert _format_time_value("22:30") == "22:30"
    assert _format_time_value(630) == "10:30"
    assert _format_time_value(2230) == "22:30"
    assert first_prop({"masterSleepStartTime": "21:00"}, ("masterSleepStartTime",))[0] == "21:00"
    assert raw_to_time(630) == time(10, 30)
    assert encode_time(time(22, 30), "minutes") == 22 * 60 + 30
    payload = resolve_write_payload(
        {"masterSleepStartTime": 1320},
        ("masterSleepStartTime",),
        "masterSleepStartTime",
        time(23, 0),
    )
    assert payload == {"masterSleepStartTime": 23 * 60}


def test_all_entities_enabled_by_default():
    coord = _coord()
    analytics = _analytics()
    entities = sensor_entities_for_device(
        coord, coord, analytics, coord.data["devices"][0]
    )
    entities += [FurbulousSleepModeSensor(coord, 1)]
    entities += schedule_time_entities(coord, MagicMock(), 1, "iot-1")
    disabled = [
        e
        for e in entities
        if getattr(e, "entity_registry_enabled_default", True) is False
    ]
    assert disabled == []


def test_screen_mode_not_switch():
    switches = switch_entities_for_device(
        _coord(), MagicMock(), _coord().data["devices"][0]
    )
    assert not any(s.translation_key == "screen_off" for s in switches)
    buttons = button_entities_for_device(
        _coord(), MagicMock(), _coord().data["devices"][0]
    )
    assert not any(b.translation_key in ("screen_on", "screen_off") for b in buttons)
    mirror = FurbulousSleepModeSensor(_coord(), 1)
    assert mirror.entity_registry_enabled_default is True


def test_empty_state_policy():
    """Text uses -; counts use 0; duration/weight None is allowed (HA unknown)."""
    from custom_components.furbulous.analytics_entities import AnalyticsBoxSensor
    from homeassistant.components.sensor import SensorStateClass

    coord = _coord()
    analytics = MagicMock()
    analytics.metrics_for_device.return_value = {}
    analytics.async_add_listener = MagicMock(return_value=lambda: None)

    count = AnalyticsBoxSensor(
        coord,
        analytics,
        coord.data["devices"][0],
        translation_key="visits_30_days",
        unique_suffix="v30",
        metric_key="visits_30d",
        state_class=SensorStateClass.MEASUREMENT,
    )
    assert count.native_value == 0

    from custom_components.furbulous.live_extra_sensors import FurbulousFirmwareSensor

    assert FurbulousFirmwareSensor(coord, 1).native_value  # version or -
