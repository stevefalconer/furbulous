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
