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
    "errorReportEvent": 0,
    "masterSleepStartTime": "22:00",
    "masterSleepEndTime": 630,  # 10:30 as minutes
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
    for key in ("full_auto_mode", "do_not_disturb", "screen_off", "child_lock"):
        cat = by_key[key].entity_category
        assert cat is not None and "config" in str(cat).lower()
    assert by_key["empty_confirm_ready"].entity_category is None


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
    coord_cov = _coord({"errorReportEvent": 128})
    assert FurbulousCoverOpenSensor(coord_cov, 1).is_on is True
    coord_dr = _coord({"errorReportEvent": 64})
    assert FurbulousDrawerNotInPlaceSensor(coord_dr, 1).is_on is True


def test_box_action_labels():
    for code, label in (
        (0, "Idle"),
        (1, "Cleaning"),
        (2, "Emptying"),
        (3, "Packing bag"),
        (4, "Paused"),
        (5, "Resuming"),
    ):
        s = FurbulousHandModeSensor(_coord({"handMode": code}), 1)
        assert s.native_value == label
    assert FurbulousHandModeSensor(_coord({"handMode": 1}), 1).translation_key == "box_action"


def test_cycle_completion_mapping():
    s = FurbulousCompletionStatusSensor(_coord({"completionStatus": 1}), 1)
    assert s.native_value == "Complete"
    assert s.extra_state_attributes["raw_completion_status"] == 1
    assert FurbulousCompletionStatusSensor(_coord({}), 1).native_value == "-"


def test_screen_off_and_quiet_hours_time_entities_writable():
    coord = _coord()
    api = MagicMock()
    entities = schedule_time_entities(coord, api, 1, "iot-1")
    by_key = {e.translation_key: e for e in entities}
    assert set(by_key) == {
        "screen_off_start",
        "screen_off_end",
        "quiet_hours_start",
        "quiet_hours_end",
    }
    assert by_key["screen_off_start"].native_value == time(22, 0)
    assert by_key["screen_off_end"].native_value == time(10, 30)
    assert "config" in str(by_key["screen_off_start"].entity_category).lower()
    # Defaults when properties empty
    empty = schedule_time_entities(_coord({}), api, 1, "iot-1")
    assert empty[0].native_value == time(22, 0)


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


def test_screen_off_single_control():
    switches = switch_entities_for_device(
        _coord(), MagicMock(), _coord().data["devices"][0]
    )
    screen = [s for s in switches if s.translation_key == "screen_off"]
    assert len(screen) == 1
    buttons = button_entities_for_device(
        _coord(), MagicMock(), _coord().data["devices"][0]
    )
    assert not any(b.translation_key in ("screen_on", "screen_off") for b in buttons)
    # Diagnostic mirror enabled
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
