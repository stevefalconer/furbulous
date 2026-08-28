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
        runtime = getattr(self.config_entry, "runtime_data", None)
        pause = getattr(runtime, "poll_pause", None) if runtime else None
        # Use `is True` so test MagicMocks are not treated as paused.
        if pause is not None and getattr(pause, "is_paused", False) is True:
            if self.data is not None:
                return self.data
            return {"devices": [], "pets": []}
        try:
            data = await self.api.async_get_full_snapshot(
                prior_devices=(self.data or {}).get("devices")
            )
        except FurbulousCatAuthError as err:
            self._mark_unavailable()
            raise ConfigEntryAuthFailed from err
        except FurbulousCatConnectionError as err:
            self._mark_unavailable()
            raise UpdateFailed(str(err)) from err

        self._mark_available()
        self._async_prune_stale_devices(data)
        # Analytics: full recompute on 5 min path (hours-since gauges, pets)
        if runtime is not None:
            eng = getattr(runtime, "analytics", None)
            if eng is not None:
                eng.process_snapshot(
                    data.get("devices") or [],
                    pets=data.get("pets"),
                    full_recompute=True,
                )
                eng.schedule_flush()
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
        """Remove HA box/pet devices no longer reported by the cloud.

        Never prune the account **hub** device (``hub_<entry_id>``): it is not
        in the cloud device list. Pruning it deleted Pause / Resume entities
        on the first full refresh after Resume.
        """
        entry = self.config_entry
        if entry is None:
            return
        current_ids = {
            str(device.get("id"))
            for device in (data.get("devices") or [])
            if device.get("id") is not None
        }
        # Also keep pets currently in snapshot
        for pet in data.get("pets") or []:
            pid = pet.get("id")
            if pid is not None:
                current_ids.add(f"pet_{pid}")

        device_reg = dr.async_get(self.hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_reg, entry.entry_id
        ):
            furbulous_ids = {
                ident[1]
                for ident in device_entry.identifiers
                if ident[0] == DOMAIN
            }
            # Hub is local-only (pause polling controls) — never a cloud box/pet.
            if any(str(ident).startswith("hub_") for ident in furbulous_ids):
                continue
            # Prune boxes and pets no longer on the account
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

        Interval: 30 s — occupancy, weight, full/errors, and display mode.
        Calls properties/get per known iotid; pet/list at most every 24 h
        (cached). No device list or daily stats (5 min full poll).
        """
        runtime = getattr(self.config_entry, "runtime_data", None)
        pause = getattr(runtime, "poll_pause", None) if runtime else None
        if pause is not None and getattr(pause, "is_paused", False) is True:
            if self.data is not None:
                return self.data
            return {"devices": []}
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

        # Visit / full edges + pet roster (properties already ~30s; pets added)
        if runtime is not None:
            eng = getattr(runtime, "analytics", None)
            if eng is not None:
                eng.process_snapshot(
                    data.get("devices") or [],
                    pets=data.get("pets"),
                    full_recompute=False,
                )
                eng.schedule_flush()
        return data

    def _mark_unavailable(self) -> None:
        """Log once when presence polling fails (avoid spam)."""
        if not self._unavailable_logged:
            _LOGGER.warning(
                "Furbulous presence poll failed (region=%s); will retry",
                self.api.region_id,
            )
            self._unavailable_logged = True
