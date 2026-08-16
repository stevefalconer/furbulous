"""UAT scenarios: cat-parent workflows and FAQ answers as executable tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.furbulous.analytics_entities import LastVisitActivitySensor
from custom_components.furbulous.button import FurbulousHandModeButton
from custom_components.furbulous.device_entities import button_entities_for_device
from custom_components.furbulous.empty_safety import arm_empty, disarm_empty
from custom_components.furbulous.switch import (
    FurbulousEnergySavingSwitch,
    FurbulousFullAutoModeSwitch,
)


def _coord(props=None):
    c = MagicMock()
    c.data = {
        "devices": [
            {
                "id": 7,
                "iotid": "iot-7",
                "name": "Living Room",
                "properties": props
                or {
                    "masterSleepOnOff": 0,
                    "FullAutoModeSwitch": 1,
                    "handMode": 0,
                },
            }
        ]
    }
    c.last_update_success = True
    c.async_request_refresh = AsyncMock()
    return c


def test_screen_off_on_means_display_off():
    """UAT: enabling Screen off turns screen off; disabling leaves screen on."""
    coord = _coord({"masterSleepOnOff": 1})
    sw = FurbulousEnergySavingSwitch(coord, MagicMock(), 7, "iot-7")
    assert sw.is_on is True  # ON = screen off
    assert sw.extra_state_attributes["when_on"] == "screen_off_or_dimmed"
    assert sw.extra_state_attributes["when_off"] == "screen_on_normal"

    coord_on = _coord({"masterSleepOnOff": 0})
    sw2 = FurbulousEnergySavingSwitch(coord_on, MagicMock(), 7, "iot-7")
    assert sw2.is_on is False


def test_full_auto_vs_pause_docs():
    """UAT: Auto-clean is policy; Pause/Resume are in-cycle controls."""
    sw = FurbulousFullAutoModeSwitch(_coord(), MagicMock(), 7, "iot-7")
    attrs = sw.extra_state_attributes
    note = (attrs.get("note") or "") + (attrs.get("plain_english") or "")
    assert "Pause" in note or "pause" in note.lower() or "Clean now" in note
    buttons = button_entities_for_device(_coord(), MagicMock(), _coord().data["devices"][0])
    keys = {b.translation_key for b in buttons}
    assert "pause_cleaning" in keys
    assert "resume_cleaning" in keys
    assert "manual_clean" in keys


@pytest.mark.asyncio
async def test_empty_requires_confirm_ready():
    """UAT: Empty blocked without Empty confirm ready; works when armed."""
    coord = _coord()
    api = MagicMock()
    api.set_device_property = AsyncMock(return_value=True)
    btn = FurbulousHandModeButton(
        coord,
        api,
        7,
        "iot-7",
        translation_key="empty",
        unique_id="iot-7_dump",
        hand_mode=2,
        icon="mdi:delete-empty",
        analytics=None,
    )
    disarm_empty(7)
    with pytest.raises(HomeAssistantError):
        await btn.async_press()
    arm_empty(7)
    await btn.async_press()
    api.set_device_property.assert_awaited()


def test_last_visit_activity_includes_pet():
    """UAT: Activity-friendly sensor includes pet name when identified."""
    coord = _coord()
    analytics = MagicMock()
    analytics.last_visitor.return_value = "Luna"
    analytics.last_visit_ts.return_value = 1_700_000_000.0
    analytics.async_add_listener = MagicMock(return_value=lambda: None)
    sensor = LastVisitActivitySensor(coord, analytics, coord.data["devices"][0])
    # May include timezone formatting; pet name must appear
    assert "Luna" in str(sensor.native_value)


def test_controls_only_chore_buttons_and_empty_arm():
    """UAT: Controls keep Empty + confirm + clean actions; settings are CONFIG."""
    from custom_components.furbulous.device_entities import switch_entities_for_device

    switches = switch_entities_for_device(
        _coord(), MagicMock(), _coord().data["devices"][0]
    )
    control_switches = [s for s in switches if s.entity_category is None]
    keys = {s.translation_key for s in control_switches}
    assert keys == {"empty_confirm_ready"}
