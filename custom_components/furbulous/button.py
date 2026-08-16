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
from .entity_ids import UID_LITTER_REFILLED, box_uid
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

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Warn on Empty about litter dump and closed drum."""
        if self._hand_mode != 2:
            return None
        return {
            "warning": (
                "Empty waste dumps all litter from the globe. Confirm the litter "
                "drum is closed, turn ON “Empty — confirm ready”, then press "
                "Empty waste within 90 seconds."
            ),
            "requires": "empty_confirm_ready",
            "plain_english": "Dumps the litter — only after Empty — confirm ready.",
            "audience": "chore",
            "vendor_property": "handMode",
            "raw_hand_mode": "2",
        }

    async def async_press(self) -> None:
        """Send handMode command (user action — not a poll)."""
        # Empty (handMode 2): require “Confirm empty ready” switch armed
        if self._hand_mode == 2:
            from .empty_safety import consume_empty_arm

            if not consume_empty_arm(self._device_id):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="empty_not_confirmed",
                )  # message references Empty confirm ready

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
            unique_id=box_uid(device_id, UID_LITTER_REFILLED),
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


