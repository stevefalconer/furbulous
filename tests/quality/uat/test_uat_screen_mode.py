"""UAT: Screen mode (DisplaySwitch) + schedule model."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.furbulous.schedule_props import (
    in_overnight_window,
    is_display_blanked,
)
from custom_components.furbulous.select import (
    SCREEN_MODE_ALWAYS_ON,
    SCREEN_MODE_SCHEDULED,
    FurbulousScreenModeSelect,
)
from custom_components.furbulous.analytics.pet_match import (
    extract_pet_weight_grams,
    resolve_visit_identity,
)


def test_display_blanked_model():
    """DisplaySwitch 0 = never blank; 1 = blank inside local window."""
    assert is_display_blanked({"DisplaySwitch": 0, "displayStartTime": 0, "displayEndTime": 1439}) is False
    # Force scheduled full-day style
    assert is_display_blanked({"DisplaySwitch": 1, "displayStartTime": 0, "displayEndTime": 0}) is True
    # Overnight 23:00-07:00
    props = {"DisplaySwitch": 1, "displayStartTime": 1380, "displayEndTime": 420}
    assert in_overnight_window(1420, 1380, 420) is True  # 23:40
    assert in_overnight_window(100, 1380, 420) is True  # 01:40
    assert in_overnight_window(720, 1380, 420) is False  # 12:00


def test_screen_mode_select_maps_display_switch():
    coord = MagicMock()
    coord.data = {
        "devices": [
            {
                "id": 1,
                "iotid": "iot",
                "properties": {"DisplaySwitch": 0},
            }
        ]
    }
    coord.last_update_success = True
    api = MagicMock()
    api.set_device_property = AsyncMock(return_value=True)
    sel = FurbulousScreenModeSelect(coord, api, 1, "iot")
    assert sel.current_option == SCREEN_MODE_ALWAYS_ON

    coord.data["devices"][0]["properties"]["DisplaySwitch"] = 1
    assert sel.current_option == SCREEN_MODE_SCHEDULED


@pytest.mark.asyncio
async def test_screen_mode_writes_display_switch():
    coord = MagicMock()
    coord.data = {"devices": [{"id": 1, "iotid": "iot", "properties": {"DisplaySwitch": 0}}]}
    coord.last_update_success = True
    coord.async_request_refresh = AsyncMock()
    api = MagicMock()
    api.set_device_property = AsyncMock(return_value=True)
    sel = FurbulousScreenModeSelect(coord, api, 1, "iot")
    await sel.async_select_option(SCREEN_MODE_SCHEDULED)
    api.set_device_property.assert_awaited_with("iot", {"DisplaySwitch": 1})
    await sel.async_select_option(SCREEN_MODE_ALWAYS_ON)
    api.set_device_property.assert_awaited_with("iot", {"DisplaySwitch": 0})
    assert coord.data["devices"][0]["properties"]["DisplaySwitch"] == 0


def test_all_language_packs_translate_screen_mode_options():
    root = Path(__file__).resolve().parents[3] / "custom_components" / "furbulous" / "translations"
    packs = list(root.glob("*.json"))
    assert packs
    for path in packs:
        data = json.loads(path.read_text())
        state = data["entity"]["select"]["screen_mode"]["state"]
        assert data["entity"]["binary_sensor"]["trash_door_blocked"]["name"]
        assert set(state) == {"always_on", "scheduled"}
        assert state["always_on"].strip()
        assert state["scheduled"].strip()
        if path.name != "en.json":
            assert state["always_on"] != "Always on" or state["scheduled"] != "Scheduled"


def test_pet_unit_1_is_pounds_for_us_roster():
    """Jet 17 unit=1 → ~17 lb in grams; matches WC visit weights."""
    jet = {"nickname": "Jet", "weight": 17, "unit": 1, "pet_id": 1}
    tigger = {"nickname": "Tigger", "weight": 24, "unit": 1, "pet_id": 2}
    g_jet = extract_pet_weight_grams(jet)
    g_tig = extract_pet_weight_grams(tigger)
    assert g_jet == pytest.approx(17 * 453.59237)
    assert g_tig == pytest.approx(24 * 453.59237)
    pets = [
        {"id": 1, "name": "Jet", "weight": 17, "unit": 1},
        {"id": 2, "name": "Tigger", "weight": 24, "unit": 1},
    ]
    m = resolve_visit_identity({}, 7882.0, pets, {})
    assert m.display_name == "Jet"
    m2 = resolve_visit_identity({}, 10805.0, pets, {})
    assert m2.display_name == "Tigger"
