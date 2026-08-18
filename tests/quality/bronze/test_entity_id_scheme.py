"""Bronze: cat-parent unique_id scheme is consistent and readable."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.furbulous.device_entities import (
    binary_sensor_entities_for_device,
    button_entities_for_device,
    select_entities_for_device,
    sensor_entities_for_device,
    switch_entities_for_device,
)
from custom_components.furbulous.entity_ids import box_uid, pet_uid


def _coord():
    c = MagicMock()
    c.data = {
        "devices": [
            {
                "id": 42,
                "iotid": "iot-42",
                "name": "Box",
                "version": "1.0",
                "properties": {
                    "catWeight": 4000,
                    "workstatus": 0,
                    "handMode": 0,
                    "completionStatus": 1,
                    "masterSleepOnOff": 0,
                    "childLockOnOff": 0,
                    "FullAutoModeSwitch": 1,
                    "errorReportEvent": 0,
                    "catCleanOnOff": 5,
                },
                "daily_stats": {"times": 1, "avg_duration": 20},
                "device_online": 1,
                "is_disturb": 0,
            }
        ],
        "pets": [],
    }
    c.last_update_success = True
    return c


def test_box_uid_format():
    assert box_uid(42, "last_cat") == "furbulous_42_last_cat"
    assert pet_uid("9", "visits_30_days") == "furbulous_pet_9_visits_30_days"


def test_all_box_unique_ids_use_cat_parent_scheme():
    coord = _coord()
    analytics = MagicMock()
    analytics.metrics_for_device.return_value = {}
    analytics.occupying_pet.return_value = "-"
    analytics.last_visitor.return_value = "-"
    analytics.last_visit_ts.return_value = None
    analytics.last_visit_weight_g.return_value = None
    analytics.last_clean_ts.return_value = None
    analytics.last_clean_cat.return_value = "-"
    analytics.toilet_status.return_value = {
        "label": "Idle",
        "severity": "ok",
        "awaiting_clean": False,
        "seconds_since_visit": None,
    }
    analytics.needs_cleaning.return_value = False
    analytics.async_add_listener = MagicMock(return_value=lambda: None)
    analytics._device_state = {}
    device = coord.data["devices"][0]

    entities = []
    entities += sensor_entities_for_device(coord, coord, analytics, device)
    entities += binary_sensor_entities_for_device(
        coord, coord, device, analytics=analytics
    )
    entities += switch_entities_for_device(coord, MagicMock(), device)
    entities += button_entities_for_device(coord, MagicMock(), device, analytics)
    entities += select_entities_for_device(coord, MagicMock(), device)
    # screen_mode is a select entity

    expected_slugs = {
        "last_cat",
        "needs_emptying",
        "needs_cleaning",
        "toilet_status",
        "last_cleaned",
        "cat_inside",
        "clean_now",
        "empty_waste",
        "seal_waste_bag",
        "empty_confirm_ready",
        "auto_clean_after_visits",
        "quiet_hours",
        "screen_mode",
        "bag_age_hours",
        "litter_age_hours",
        "what_box_doing",
        "cat_weight",
        "uses_today",
    }
    uids = {e.unique_id for e in entities}
    for slug in expected_slugs:
        assert f"furbulous_42_{slug}" in uids, slug

    # No vendor camelCase or old iotid-prefix control ids
    joined = " ".join(uids)
    assert "catWeight" not in joined
    assert "handMode" not in joined
    assert "errorReportEvent" not in joined
    assert not any(uid.startswith("iot-") for uid in uids)
