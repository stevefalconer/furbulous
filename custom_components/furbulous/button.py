"""Button platform for Furbulous."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FurbulousEntity
from .helpers import async_add_devices_listener

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons; dynamically add for new devices."""
    from .device_entities import button_entities_for_device

    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    api = runtime.api
    analytics = runtime.analytics
    known: set = set()

    def build(device: dict) -> list:
        return button_entities_for_device(coordinator, api, device, analytics)

    listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known
    )
    entry.async_on_unload(coordinator.async_add_listener(listener))
    listener()


class FurbulousHandModeButton(FurbulousEntity, ButtonEntity):
    """Button that sets a handMode property value via shared API."""

    def __init__(
        self,
        coordinator,
        api,
        device_id: int,
        iotid: str,
        *,
        translation_key: str,
        unique_id: str,
        hand_mode: int,
        icon: str,
        analytics=None,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            device_id,
            translation_key=translation_key,
            unique_id=unique_id,
        )
        self._api = api
        self._iotid = iotid
        self._hand_mode = hand_mode
        self._attr_icon = icon
        self._analytics = analytics

    async def async_press(self) -> None:
        """Send handMode command (user action — not a poll)."""
        _LOGGER.debug(
            "handMode=%s iotid=%s", self._hand_mode, self._iotid
        )
        if not await self._api.set_device_property(
            self._iotid, {"handMode": self._hand_mode}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        if self._analytics is not None:
            self._analytics.record_hand_mode(
                self._device_id, self._iotid, self._hand_mode, source="ha_button"
            )
            await self._analytics.async_flush()
        await self.coordinator.async_request_refresh()


class FurbulousLitterResetButton(FurbulousEntity, ButtonEntity):
    """Mark litter reset after topping up (analytics helper if API unknown)."""

    _attr_icon = "mdi:shovel"

    def __init__(
        self,
        coordinator,
        device_id: int,
        iotid: str,
        analytics,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="mark_litter_reset",
            unique_id=f"{iotid}_mark_litter_reset",
        )
        self._iotid = iotid
        self._analytics = analytics

    async def async_press(self) -> None:
        """Record a litter reset event for interval analytics."""
        self._analytics.record_litter_reset(
            self._device_id, self._iotid, source="ha_button"
        )
        await self._analytics.async_flush()
        self.async_write_ha_state()


class FurbulousScreenButton(FurbulousEntity, ButtonEntity):
    """Turn the box display off or on (energy-saving / standby screen).

    Uses ``masterSleepOnOff`` (same property as Energy saving). Automations can
    blank the screen except when bag full / errors need attention.
    """

    def __init__(
        self,
        coordinator,
        api,
        device_id: int,
        iotid: str,
        *,
        screen_on: bool,
    ) -> None:
        """Initialize screen on or off button."""
        key = "screen_on" if screen_on else "screen_off"
        super().__init__(
            coordinator,
            device_id,
            translation_key=key,
            unique_id=f"{iotid}_{key}",
        )
        self._api = api
        self._iotid = iotid
        self._screen_on = screen_on
        self._attr_icon = "mdi:monitor" if screen_on else "mdi:monitor-off"

    async def async_press(self) -> None:
        """Set display energy-saving off (screen on) or on (screen dim/off)."""
        # masterSleepOnOff 1 = energy saving / display dim; 0 = display normal
        value = 0 if self._screen_on else 1
        if not await self._api.set_device_property(
            self._iotid, {"masterSleepOnOff": value}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()
