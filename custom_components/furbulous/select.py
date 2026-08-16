"""Select platform for Furbulous."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FurbulousEntity, extract_prop_value
from .helpers import async_add_devices_listener

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
CLEAN_DELAY_OPTIONS = [str(i) for i in range(1, 31)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities; dynamically add for new devices."""
    from .device_entities import select_entities_for_device

    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    api = runtime.api
    known: set = set()

    def build(device: dict) -> list:
        return select_entities_for_device(coordinator, api, device)

    listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known
    )
    entry.async_on_unload(coordinator.async_add_listener(listener))
    listener()


class FurbulousCleanDelaySelect(FurbulousEntity, SelectEntity):
    """Auto-clean delay select (1–30 minutes)."""

    _attr_icon = "mdi:timer-outline"
    _attr_options = CLEAN_DELAY_OPTIONS
    # No entity_category → shows under Controls with switches/buttons

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="cleaning_delay",
            unique_id=f"{iotid}_clean_delay",
        )
        self._api = api
        self._iotid = iotid

    @property
    def current_option(self) -> str | None:
        """Return current delay in minutes as string option."""
        device = self.device_data
        if not device:
            return None
        delay_value = extract_prop_value(
            (device.get("properties") or {}).get("catCleanOnOff")
        )
        if delay_value is None:
            return None
        try:
            minutes = int(delay_value)
        except (TypeError, ValueError):
            return None
        if 1 <= minutes <= 30:
            return str(minutes)
        return None

    async def async_select_option(self, option: str) -> None:
        """Set clean delay minutes."""
        try:
            delay_minutes = int(option)
        except ValueError:
            _LOGGER.debug("Invalid delay option: %s", option)
            return

        if not 1 <= delay_minutes <= 30:
            return

        if not await self._api.set_device_property(
            self._iotid, {"catCleanOnOff": delay_minutes}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()
