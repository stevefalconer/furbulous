"""Real HA environment tests for analytics entities, pets, and buttons."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.furbulous.const import CONF_REGION, DOMAIN

pytestmark = pytest.mark.asyncio


def _snapshot() -> dict:
    return {
        "authenticated": True,
        "identity_id": "id-1",
        "region": "us",
        "devices": [
            {
                "id": 42,
                "iotid": "iot-1",
                "name": "Upstairs Box",
                "device_online": 1,
                "product_name": "Furbulous Box",
                "version": "2.1.0",
                "active_time": 1700000000,
                "properties": {
                    "catWeight": 4500,
                    "workstatus": 0,
                    "errorReportEvent": 0,
                    "FullAutoModeSwitch": 1,
                    "childLockOnOff": 0,
                    "masterSleepOnOff": 0,
                    "catCleanOnOff": 5,
                    "handMode": 0,
                    "completionStatus": 1,
                },
                "daily_stats": {
                    "times": 4,
                    "avg_duration": 30,
                    "times_diff": 0,
                    "avg_diff": 1,
                },
            }
        ],
        "pets": [{"id": 9, "name": "Mochi"}],
    }


async def _setup(hass: HomeAssistant, snapshot: dict | None = None) -> MockConfigEntry:
    hass.config.units = US_CUSTOMARY_SYSTEM
    snap = snapshot or _snapshot()
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="analytics@example.com_us",
        data={
            CONF_EMAIL: "analytics@example.com",
            CONF_PASSWORD: "secret",
            CONF_REGION: "us",
            "account_type": 1,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    async def _get_devices(self, *a, **k):
        devices = snap["devices"]
        self._known_devices = [
            {"id": d.get("id"), "iotid": d.get("iotid"), "name": d.get("name")}
            for d in devices
            if d.get("iotid")
        ]
        return devices

    with (
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.authenticate",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.get_devices",
            new=_get_devices,
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.async_get_full_snapshot",
            new_callable=AsyncMock,
            return_value=snap,
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.async_get_presence_snapshot",
            new_callable=AsyncMock,
            return_value={"devices": snap["devices"]},
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.set_device_property",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_ha_setup_creates_analytics_and_pet_entities(
    hass: HomeAssistant,
) -> None:
    entry = await _setup(hass)
    entity_ids = {s.entity_id for s in hass.states.async_all()}

    # Live / chore-related entities exist
    joined = " ".join(entity_ids)
    assert "waste_bin_full" in joined or any(
        "waste" in e for e in entity_ids
    )
    assert any("cat_weight" in e or "catweight" in e.replace("_", "") for e in entity_ids)

    # Analytics sensors (translation keys → entity names)
    assert any("visits_30" in e or "visits_30_days" in e for e in entity_ids) or any(
        "30_days" in e or "30d" in e for e in entity_ids
    )

    # Pet device sensors
    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    pet_devices = [
        d
        for d in dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
        if any(str(i[1]).startswith("pet_") for i in d.identifiers)
    ]
    assert pet_devices, "expected pet device in registry"
    assert pet_devices[0].name == "Mochi"

    # Runtime analytics engine present
    assert entry.runtime_data.analytics is not None
    assert entry.runtime_data.analytics.store is not None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_pack_and_empty_record_analytics_events(
    hass: HomeAssistant,
) -> None:
    entry = await _setup(hass)
    analytics = entry.runtime_data.analytics

    # Simulate HA buttons without cloud flakiness
    analytics.record_hand_mode(42, "iot-1", 3, source="ha_button")  # pack
    analytics.record_hand_mode(42, "iot-1", 2, source="ha_button")  # empty
    await analytics.async_flush(force=True)

    packs = analytics.store.events_for_device(42, event_types={"pack"})
    bags = analytics.store.events_for_device(42, event_types={"bag_replaced"})
    assert len(packs) == 1
    assert len(bags) == 1

    metrics = analytics.metrics_for_device(42)
    assert metrics.get("packs_30d") == 1
    assert metrics.get("bags_replaced_30d") == 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_litter_reset_button_event(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    analytics = entry.runtime_data.analytics
    analytics.record_litter_reset(42, "iot-1")
    assert len(analytics.store.events_for_device(42, event_types={"litter_reset"})) == 1
    assert analytics.metrics_for_device(42).get("litter_resets_30d") == 1
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_visit_edge_via_presence_snapshot(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    analytics = entry.runtime_data.analytics
    # Occupy
    analytics.process_snapshot(
        [
            {
                "id": 42,
                "iotid": "iot-1",
                "name": "Upstairs Box",
                "properties": {
                    "workstatus": 1,
                    "errorReportEvent": 0,
                    "petName": "Mochi",
                },
            }
        ]
    )
    assert analytics.occupying_pet(42) == "Mochi"
    # End visit after debounce window
    analytics._device_state["42"]["occupy_since"] = (
        analytics._device_state["42"]["occupy_since"] - 60
    )
    analytics.process_snapshot(
        [
            {
                "id": 42,
                "iotid": "iot-1",
                "name": "Upstairs Box",
                "properties": {"workstatus": 0, "errorReportEvent": 0},
            }
        ]
    )
    visits = analytics.store.events_for_device(42, event_types={"visit_ended"})
    assert len(visits) == 1
    assert visits[0]["payload"].get("pet_name") == "Mochi"
    assert analytics.last_visitor(42) == "Mochi"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_diagnostics_include_analytics(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    from custom_components.furbulous.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    data = await async_get_config_entry_diagnostics(hass, entry)
    assert "analytics" in data
    assert "event_count" in data["analytics"]
    assert "password" not in str(data.get("entry", {})).lower() or "secret" not in str(
        data["entry"]
    )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_ha_firmware_and_cover_entities_exist(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    ids = " ".join(s.entity_id for s in hass.states.async_all())
    # firmware diagnostic sensor
    assert "firmware" in ids or any(
        "firmware" in (s.name or "").lower() for s in hass.states.async_all()
    )
    binary = " ".join(s.entity_id for s in hass.states.async_all("binary_sensor"))
    assert "cover" in binary or "drawer" in binary or "waste" in binary

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
