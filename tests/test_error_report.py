"""Waste-full / errorReportEvent decoding (live 2026-08-16: Upstairs=32)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.furbulous.binary_sensor import FurbulousWasteBinFullSensor
from custom_components.furbulous.error_report import (
    describe_error,
    is_cover_open,
    is_drawer_out,
    is_trash_door_blocked,
    is_waste_full,
)
from custom_components.furbulous.sensor import FurbulousErrorSensor


def _coord(code):
    c = MagicMock()
    c.last_update_success = True
    c.data = {
        "devices": [{"id": 4796, "iotid": "x", "properties": {"errorReportEvent": code}}]
    }
    return c


def test_waste_full_accepts_16_and_32():
    assert is_waste_full(0) is False
    assert is_waste_full(16) is True
    assert is_waste_full(32) is True
    assert is_waste_full({"value": 32, "time": 1}) is True
    # Combined bits still count as full
    assert is_waste_full(16 | 64) is True
    assert is_waste_full(32 | 64) is True
    assert is_waste_full(64) is False
    assert is_waste_full(4096) is False


def test_cover_is_lid_off_or_documented_128():
    assert is_cover_open(128) is True
    assert is_cover_open(32 | 128) is True
    assert is_cover_open(512) is True
    assert is_cover_open(32) is False
    assert is_cover_open(64) is False


def test_no_bag_uses_cover_bits_when_not_full():
    """Live Downstairs: No Bag screen → Cover open (512), needs_emptying off."""
    from custom_components.furbulous.error_report import is_no_bag

    assert is_no_bag(0) is False
    assert is_no_bag(512) is True
    assert is_no_bag(128) is True
    assert is_no_bag(32) is False  # full takes priority
    assert is_no_bag(32 | 512) is False


def test_drawer_out_not_published():
    assert is_drawer_out(0) is False
    assert is_drawer_out(64) is False
    assert is_drawer_out(16 | 64) is False
    assert is_drawer_out(524352) is False


def test_trash_door_e4():
    jammed = 64 | 524288
    assert is_trash_door_blocked(jammed) is True
    assert is_trash_door_blocked(64) is False
    assert is_drawer_out(jammed) is False
    text = describe_error(jammed)
    assert "Trash door blocked" in text
    assert "Drawer" not in text
    from custom_components.furbulous.binary_sensor import FurbulousTrashDoorSensor
    from custom_components.furbulous.error_report import TRASH_DOOR_CAUSE, TRASH_DOOR_FIX

    sensor = FurbulousTrashDoorSensor(_coord(jammed), 4796)
    attrs = sensor.extra_state_attributes
    assert "waste door" in attrs["likely_cause"].lower() or "clump" in attrs["likely_cause"].lower()
    assert "OK" in attrs["when_problem"]
    assert TRASH_DOOR_CAUSE in attrs["likely_cause"]
    assert "Resume" in TRASH_DOOR_FIX or "Clean" in TRASH_DOOR_FIX


def test_describe_error_maps_32_to_litter_full():
    assert describe_error(0) == "No error"
    assert describe_error(16) == "Litter full - Need to empty"
    assert describe_error(32) == "Litter full - Need to empty"
    assert "Litter full" in describe_error(32 | 64)
    assert "Drawer" not in describe_error(32 | 64)
    assert describe_error(512) == "Cover / lid off"


def test_needs_emptying_entity_on_for_upstairs_code_32():
    sensor = FurbulousWasteBinFullSensor(_coord(32), 4796)
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["error_code"] == "32"
    assert FurbulousWasteBinFullSensor(_coord(0), 4796).is_on is False


@pytest.mark.asyncio
async def test_litter_reset_button_sends_hand_mode_6():
    from custom_components.furbulous.button import (
        HAND_MODE_LITTER_RESET,
        FurbulousLitterResetButton,
    )

    coord = _coord(0)
    coord.config_entry = None
    api = MagicMock()
    api.set_device_property = AsyncMock(return_value=True)
    analytics = MagicMock()
    analytics.record_litter_reset = MagicMock()
    analytics.record_hand_mode = MagicMock()
    analytics.async_flush = AsyncMock()
    btn = FurbulousLitterResetButton(coord, api, 4796, "iot", analytics)
    btn.async_write_ha_state = MagicMock()
    await btn.async_press()
    api.set_device_property.assert_awaited_with("iot", {"handMode": HAND_MODE_LITTER_RESET})
    assert HAND_MODE_LITTER_RESET == 6
    analytics.record_litter_reset.assert_called_once()


def test_cat_present_ignores_clean_and_e4():
    from custom_components.furbulous.helpers import is_cat_present

    assert is_cat_present({"workstatus": 1, "completionStatus": 1}) is True
    assert is_cat_present({"workstatus": 1, "completionStatus": 3}) is False
    assert is_cat_present({"workstatus": 1, "errorReportEvent": 64 | 524288}) is False
    assert is_cat_present({"workstatus": 0}) is False
    assert is_cat_present({"workstatus": 8}) is False


def test_error_sensor_text_for_32():
    sensor = FurbulousErrorSensor(_coord(32), 4796)
    assert sensor.native_value == "Litter full - Need to empty"
