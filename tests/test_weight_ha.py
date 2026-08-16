"""Real Home Assistant environment tests for cat weight lb/kg display.

Requires: homeassistant + pytest-homeassistant-custom-component.
Verifies the entity state unit and numeric value after full integration setup
under US Customary and Metric unit systems — never grams in the UI.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.furbulous.const import CONF_REGION, DOMAIN

pytestmark = pytest.mark.asyncio

CAT_G = 4500.0
CAT_LB = CAT_G / 453.59237
CAT_KG = 4.5


def _snapshot(weight_g: float = CAT_G) -> dict:
    return {
        "authenticated": True,
        "identity_id": "id-1",
        "region": "us",
        "devices": [
            {
                "id": 42,
                "iotid": "iot-weight-1",
                "name": "Living Room Box",
                "device_online": 1,
                "product_name": "Furbulous Box",
                "version": "1.0.0",
                "active_time": 1700000000,
                "properties": {
                    "catWeight": weight_g,
                    "workstatus": 0,
                    "errorReportEvent": 0,
                    "FullAutoModeSwitch": 1,
                    "childLockOnOff": 0,
                    "masterSleepOnOff": 0,
                    "catCleanOnOff": 5,
                    "handMode": 0,
                    "completionStatus": 0,
                },
                "daily_stats": {
                    "times": 3,
                    "avg_duration": 20,
                    "times_diff": 1,
                    "avg_diff": -2,
                },
            }
        ],
        "pets": [{"id": 1, "name": "Mochi"}],
    }


async def _setup_entry(hass: HomeAssistant, snapshot: dict) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="weight@example.com_us",
        data={
            CONF_EMAIL: "weight@example.com",
            CONF_PASSWORD: "secret",
            CONF_REGION: "us",
            "account_type": 1,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.authenticate",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.async_get_full_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.async_get_presence_snapshot",
            new_callable=AsyncMock,
            return_value={"devices": snapshot["devices"]},
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


def _weight_states(hass: HomeAssistant) -> list:
    return [
        s
        for s in hass.states.async_all("sensor")
        if s.entity_id.endswith("_cat_weight")
        or "cat_weight" in s.entity_id
        or (
            s.attributes.get("device_class") == "weight"
            and "furbulous" in (s.entity_id or "")
        )
    ]


def _find_weight_state(hass: HomeAssistant):
    # unique_id fragment catWeight → entity often sensor.living_room_box_cat_weight
    for state in hass.states.async_all("sensor"):
        if state.attributes.get("device_class") == "weight":
            return state
        if "cat_weight" in state.entity_id or "catweight" in state.entity_id.replace(
            "_", ""
        ):
            return state
    # dump for debugging
    sensors = [s.entity_id for s in hass.states.async_all("sensor")]
    raise AssertionError(f"No weight sensor found. Sensors: {sensors}")


async def test_ha_weight_us_customary_shows_pounds_not_grams(
    hass: HomeAssistant,
) -> None:
    """US Customary → state in lb, value ~9.9, unit never g."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    assert hass.config.units.mass_unit == UnitOfMass.POUNDS

    entry = await _setup_entry(hass, _snapshot())
    state = _find_weight_state(hass)

    unit = state.attributes.get("unit_of_measurement")
    assert unit == "lb", f"expected lb, got {unit!r} state={state.state}"
    assert unit != "g"
    value = float(state.state)
    assert value == pytest.approx(CAT_LB, rel=0.01)
    # Must not be raw grams
    assert value < 50
    assert value != pytest.approx(CAT_G, rel=0.01)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_weight_metric_shows_kg_not_grams(hass: HomeAssistant) -> None:
    """Metric (HA mass_unit=g) → we still expose kg, not grams."""
    hass.config.units = METRIC_SYSTEM
    assert hass.config.units.mass_unit == UnitOfMass.GRAMS

    entry = await _setup_entry(hass, _snapshot())
    state = _find_weight_state(hass)

    unit = state.attributes.get("unit_of_measurement")
    assert unit == "kg", f"expected kg (not g), got {unit!r}"
    assert unit != "g"
    value = float(state.state)
    assert value == pytest.approx(CAT_KG, rel=0.01)
    assert value < 50
    assert value != pytest.approx(CAT_G, rel=0.01)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_weight_entity_native_matches_unit_system(
    hass: HomeAssistant,
) -> None:
    """Entity platform object uses calculated native unit/value."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = await _setup_entry(hass, _snapshot())

    # Access entity from entity registry / platform
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    weight_entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == entry.entry_id and "catWeight" in (e.unique_id or "")
    ]
    assert weight_entries, "weight entity not in registry"
    entity_id = weight_entries[0].entity_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == "lb"
    assert float(state.state) == pytest.approx(CAT_LB, rel=0.01)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
