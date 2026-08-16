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
        patch(
            "custom_components.furbulous.furbulous_api.FurbulousCatAPI.known_devices",
            new_callable=lambda: property(
                lambda self: [
                    {
                        "id": 42,
                        "iotid": "iot-1",
                        "name": "Box",
                    }
                ]
            ),
        ),
    ):
        # Populate known_devices on the real API instance after construction
        async def _auth(self_api=None, *a, **k):
            return True

        # Simpler: patch get_devices path inside snapshot already enough;
        # presence may return empty if known_devices empty — still ok for setup.
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

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
