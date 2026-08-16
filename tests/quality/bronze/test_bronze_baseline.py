"""Bronze: baseline integration contracts (stable ids, naming, no live cloud)."""
from __future__ import annotations

from unittest.mock import MagicMock

import json
from pathlib import Path

from custom_components.furbulous.device_entities import (
    binary_sensor_entities_for_device,
    button_entities_for_device,
    select_entities_for_device,
    sensor_entities_for_device,
    switch_entities_for_device,
)


def _coord(device: dict | None = None):
    c = MagicMock()
    c.data = {
        "devices": [
            device
            or {
                "id": 1,
                "iotid": "iot-1",
                "name": "Box",
                "version": "1.0",
                "properties": {
                    "catWeight": 4500,
                    "workstatus": 0,
                    "handMode": 0,
                    "completionStatus": 1,
                    "masterSleepOnOff": 0,
                    "childLockOnOff": 0,
                    "FullAutoModeSwitch": 1,
                    "errorReportEvent": 0,
                    "catCleanOnOff": 5,
                },
                "daily_stats": {"times": 3, "avg_duration": 40},
                "device_online": 1,
                "is_disturb": 0,
            }
        ],
        "pets": [],
    }
    c.last_update_success = True
    return c


def _device():
    return _coord().data["devices"][0]


def test_manifest_version_present():
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "custom_components"
            / "furbulous"
            / "manifest.json"
        ).read_text()
    )
    assert manifest["domain"] == "furbulous"
    assert manifest["version"]
    assert manifest["version"] >= "1.3.8"


def test_all_entities_have_unique_id_and_has_entity_name():
    coord = _coord()
    presence = coord
    analytics = MagicMock()
    analytics.metrics_for_device.return_value = {}
    analytics.occupying_pet.return_value = "-"
    analytics.last_visitor.return_value = "-"
    analytics.last_visit_ts.return_value = None
    analytics.last_visit_weight_g.return_value = None
    analytics.async_add_listener = MagicMock(return_value=lambda: None)
    analytics._device_state = {}

    device = _device()
    entities = []
    entities += sensor_entities_for_device(coord, presence, analytics, device)
    entities += binary_sensor_entities_for_device(coord, presence, device)
    entities += switch_entities_for_device(coord, MagicMock(), device)
    entities += button_entities_for_device(coord, MagicMock(), device, analytics)
    entities += select_entities_for_device(coord, MagicMock(), device)

    assert len(entities) >= 20
    uids = []
    for ent in entities:
        assert getattr(ent, "unique_id", None), type(ent).__name__
        assert getattr(ent, "has_entity_name", False) is True
        uids.append(ent.unique_id)
    assert len(uids) == len(set(uids)), "duplicate unique_ids"


def test_no_screen_on_off_buttons_created():
    entities = button_entities_for_device(
        _coord(), MagicMock(), _device(), analytics=None
    )
    keys = [e.translation_key for e in entities]
    assert "screen_on" not in keys
    assert "screen_off" not in keys
    assert "empty" in keys
