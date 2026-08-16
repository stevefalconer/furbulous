"""DataUpdateCoordinators for Furbulous (Pi-friendly polling)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    UPDATE_INTERVAL_FAST_SECONDS,
    UPDATE_INTERVAL_NORMAL_MINUTES,
)
from .furbulous_api import (
    FurbulousCatAPI,
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)

_LOGGER = logging.getLogger(__name__)


class FurbulousDataUpdateCoordinator(DataUpdateCoordinator):
    """Full device snapshot on a slow interval (default 5 minutes)."""

    config_entry: Any

    def __init__(
        self,
        hass: HomeAssistant,
        api: FurbulousCatAPI,
        config_entry: Any,
    ) -> None:
        """Initialize normal coordinator."""
        self.api = api
        self._unavailable_logged = False
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_NORMAL_MINUTES),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch full snapshot.

        Interval: 5 min — weight, stats, switches, errors, and device list do
        not need sub-minute freshness. Keeps cloud QPS and Pi wake work low.
        Entities never call the API; they read coordinator.data only.
        """
        try:
            data = await self.api.async_get_full_snapshot()
        except FurbulousCatAuthError as err:
            self._mark_unavailable()
            raise ConfigEntryAuthFailed from err
        except FurbulousCatConnectionError as err:
            self._mark_unavailable()
            raise UpdateFailed(str(err)) from err

        self._mark_available()
        self._async_prune_stale_devices(data)
        return data

    def _mark_unavailable(self) -> None:
        """Log once when the cloud becomes unreachable."""
        if not self._unavailable_logged:
            _LOGGER.warning(
                "Unable to reach Furbulous cloud (region=%s); will retry",
                self.api.region_id,
            )
            self._unavailable_logged = True

    def _mark_available(self) -> None:
        """Log once when connectivity is restored."""
        if self._unavailable_logged:
            _LOGGER.info(
                "Furbulous cloud connection restored (region=%s)",
                self.api.region_id,
            )
            self._unavailable_logged = False

    def _async_prune_stale_devices(self, data: dict[str, Any]) -> None:
        """Remove HA device registry entries no longer reported by the cloud."""
        entry = self.config_entry
        if entry is None:
            return
        current_ids = {
            str(device.get("id"))
            for device in (data.get("devices") or [])
            if device.get("id") is not None
        }
        device_reg = dr.async_get(self.hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_reg, entry.entry_id
        ):
            furbulous_ids = {
                ident[1]
                for ident in device_entry.identifiers
                if ident[0] == DOMAIN
            }
            if furbulous_ids and furbulous_ids.isdisjoint(current_ids):
                device_reg.async_update_device(
                    device_entry.id, remove_config_entry_id=entry.entry_id
                )


class FurbulousPresenceCoordinator(DataUpdateCoordinator):
    """Cat-in-box occupancy only on a fast interval (default 30 seconds)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FurbulousCatAPI,
        config_entry: Any,
    ) -> None:
        """Initialize presence coordinator."""
        self.api = api
        self._unavailable_logged = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_presence",
            config_entry=config_entry,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_FAST_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch presence-only snapshot.

        Interval: 30 s — cat occupancy is the only signal that benefits from
        near-real-time updates. This path calls properties/get per known iotid
        only (no device list, no daily stats, no pets). Full property maps are
        returned by the vendor in that one call; we still avoid 3× extra
        endpoints that the old dual full-poll design hit every 30 s.
        """
        if not self.api.known_devices:
            return {"devices": []}
        try:
            data = await self.api.async_get_presence_snapshot()
        except FurbulousCatAuthError as err:
            self._mark_unavailable()
            raise ConfigEntryAuthFailed from err
        except FurbulousCatConnectionError as err:
            self._mark_unavailable()
            raise UpdateFailed(str(err)) from err

        if self._unavailable_logged:
            _LOGGER.info(
                "Furbulous presence polling restored (region=%s)",
                self.api.region_id,
            )
            self._unavailable_logged = False
        return data

    def _mark_unavailable(self) -> None:
        """Log once when presence polling fails (avoid spam)."""
        if not self._unavailable_logged:
            _LOGGER.warning(
                "Furbulous presence poll failed (region=%s); will retry",
                self.api.region_id,
            )
            self._unavailable_logged = True
