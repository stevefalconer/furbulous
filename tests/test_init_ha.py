"""Integration setup/unload tests with full Home Assistant."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.furbulous.const import CONF_REGION, DOMAIN

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.asyncio


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Config entry sets up platforms and unloads cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com_us",
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_REGION: "us",
            "account_type": 1,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    snapshot = {
        "authenticated": True,
        "identity_id": "id-1",
        "region": "us",
        "devices": [
            {
                "id": 42,
                "iotid": "iot-1",
                "name": "Box",
                "device_online": 1,
                "properties": {
                    "catWeight": 4500,
                    "workstatus": 0,
                    "errorReportEvent": 0,
                    "FullAutoModeSwitch": 1,
                    "childLockOnOff": 0,
                    "masterSleepOnOff": 0,
                    "catCleanOnOff": 5,
                },
                "daily_stats": {"times": 3, "avg_duration": 20},
            }
        ],
        "pets": [{"id": 1, "name": "Mochi"}],
    }

    order: list[str] = []

    async def _get_devices(self, *a, **k):
        order.append("devices")
        self._known_devices = [
            {"id": 42, "iotid": "iot-1", "name": "Box"},
        ]
        return snapshot["devices"]

    async def _presence(self, *a, **k):
        order.append("presence")
        return {"devices": snapshot["devices"], "pets": snapshot["pets"]}

    async def _full(self, *a, **k):
        order.append("full")
        return snapshot

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
            "custom_components.furbulous.__init__.FurbulousCatAPI.async_get_presence_snapshot",
            new=_presence,
        ),
        patch(
            "custom_components.furbulous.__init__.FurbulousCatAPI.async_get_full_snapshot",
            new=_full,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert order.index("devices") < order.index("presence") < order.index("full")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failed(hass: HomeAssistant) -> None:
    """Bad credentials mark entry as setup error / retry auth."""
    from custom_components.furbulous.furbulous_api import FurbulousCatAuthError

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="bad@example.com_us",
        data={
            CONF_EMAIL: "bad@example.com",
            CONF_PASSWORD: "x",
            CONF_REGION: "us",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.furbulous.__init__.FurbulousCatAPI.authenticate",
        new_callable=AsyncMock,
        side_effect=FurbulousCatAuthError("nope"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state in (
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
    )
