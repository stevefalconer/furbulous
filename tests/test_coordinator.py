"""Coordinator error mapping and success path (no live cloud)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.furbulous.coordinator import (
    FurbulousDataUpdateCoordinator,
    FurbulousPresenceCoordinator,
)
from custom_components.furbulous.furbulous_api import (
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test-entry"
    return entry


@pytest.mark.asyncio
async def test_full_coordinator_success(mock_hass, mock_entry):
    """Successful full snapshot populates coordinator data keys."""
    api = MagicMock()
    api.region_id = "us"
    api.async_get_full_snapshot = AsyncMock(
        return_value={
            "authenticated": True,
            "identity_id": "id-1",
            "region": "us",
            "devices": [{"id": 1, "iotid": "x", "properties": {}}],
        }
    )
    coord = FurbulousDataUpdateCoordinator(mock_hass, api, mock_entry)
    with patch.object(coord, "_async_prune_stale_devices"):
        data = await coord._async_update_data()
    assert data["authenticated"] is True
    assert data["region"] == "us"
    assert len(data["devices"]) == 1
    assert coord._unavailable_logged is False
    api.async_get_full_snapshot.assert_awaited_once_with(prior_devices=None)


@pytest.mark.asyncio
async def test_full_coordinator_passes_prior_devices(mock_hass, mock_entry):
    """Full coordinator wires prior_devices from last snapshot."""
    api = MagicMock()
    api.region_id = "us"
    prior = [{"id": 1, "iotid": "x", "properties": {"catWeight": 1}}]
    api.async_get_full_snapshot = AsyncMock(
        return_value={
            "authenticated": True,
            "region": "us",
            "devices": prior,
            "pets": [],
        }
    )
    coord = FurbulousDataUpdateCoordinator(mock_hass, api, mock_entry)
    coord.data = {"devices": prior, "pets": []}
    with patch.object(coord, "_async_prune_stale_devices"):
        await coord._async_update_data()
    api.async_get_full_snapshot.assert_awaited_once_with(prior_devices=prior)


@pytest.mark.asyncio
async def test_full_coordinator_auth_failure(mock_hass, mock_entry):
    """Auth errors become ConfigEntryAuthFailed."""
    api = MagicMock()
    api.region_id = "us"
    api.async_get_full_snapshot = AsyncMock(
        side_effect=FurbulousCatAuthError("bad")
    )
    coord = FurbulousDataUpdateCoordinator(mock_hass, api, mock_entry)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()
    assert coord._unavailable_logged is True


@pytest.mark.asyncio
async def test_full_coordinator_connection_failure(mock_hass, mock_entry):
    """Connection errors become UpdateFailed (unavailable path)."""
    api = MagicMock()
    api.region_id = "us"
    api.async_get_full_snapshot = AsyncMock(
        side_effect=FurbulousCatConnectionError("down")
    )
    coord = FurbulousDataUpdateCoordinator(mock_hass, api, mock_entry)
    with pytest.raises(UpdateFailed, match="down"):
        await coord._async_update_data()
    assert coord._unavailable_logged is True
    # Second failure does not reset flag (still logged once)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert coord._unavailable_logged is True


@pytest.mark.asyncio
async def test_full_coordinator_recovery_clears_flag(mock_hass, mock_entry):
    """Successful poll after failure clears unavailable flag."""
    api = MagicMock()
    api.region_id = "us"
    api.async_get_full_snapshot = AsyncMock(
        side_effect=[
            FurbulousCatConnectionError("down"),
            {
                "authenticated": True,
                "region": "us",
                "devices": [],
            },
        ]
    )
    coord = FurbulousDataUpdateCoordinator(mock_hass, api, mock_entry)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert coord._unavailable_logged is True
    with patch.object(coord, "_async_prune_stale_devices"):
        await coord._async_update_data()
    assert coord._unavailable_logged is False


@pytest.mark.asyncio
async def test_presence_coordinator_auth_failure(mock_hass, mock_entry):
    """Presence path maps auth errors the same way."""
    api = MagicMock()
    api.region_id = "eu"
    api.known_devices = [{"id": 1, "iotid": "x"}]
    api.async_get_presence_snapshot = AsyncMock(
        side_effect=FurbulousCatAuthError("token")
    )
    coord = FurbulousPresenceCoordinator(mock_hass, api, mock_entry)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_presence_empty_when_no_known_devices(mock_hass, mock_entry):
    """Presence returns empty snapshot until main poll fills known_devices."""
    api = MagicMock()
    api.region_id = "us"
    api.known_devices = []
    coord = FurbulousPresenceCoordinator(mock_hass, api, mock_entry)
    data = await coord._async_update_data()
    assert data == {"devices": []}
    api.async_get_presence_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_prune_keeps_hub_device(mock_hass, mock_entry):
    """Hub pause device must survive full snapshot prune (not in cloud list)."""
    api = MagicMock()
    api.region_id = "us"
    coord = FurbulousDataUpdateCoordinator(mock_hass, api, mock_entry)

    hub = MagicMock()
    hub.id = "hub-dev"
    hub.identifiers = {("furbulous", "hub_test-entry")}

    stale_box = MagicMock()
    stale_box.id = "gone-box"
    stale_box.identifiers = {("furbulous", "9999")}

    live_box = MagicMock()
    live_box.id = "live-box"
    live_box.identifiers = {("furbulous", "3139")}

    device_reg = MagicMock()
    device_reg.async_update_device = MagicMock()

    with (
        patch(
            "custom_components.furbulous.coordinator.dr.async_get",
            return_value=device_reg,
        ),
        patch(
            "custom_components.furbulous.coordinator.dr.async_entries_for_config_entry",
            return_value=[hub, stale_box, live_box],
        ),
    ):
        coord._async_prune_stale_devices(
            {"devices": [{"id": 3139, "iotid": "x"}], "pets": []}
        )

    # Only the missing box is detached; hub is preserved.
    device_reg.async_update_device.assert_called_once_with(
        "gone-box", remove_config_entry_id=mock_entry.entry_id
    )
