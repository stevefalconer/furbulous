"""Switch platform for Furbulous."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FurbulousEntity, extract_prop_value
from .helpers import async_add_devices_listener

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches; dynamically add for new devices."""
    from .device_entities import switch_entities_for_device

    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    api = runtime.api
    known: set = set()

    def build(device: dict) -> list:
        return switch_entities_for_device(coordinator, api, device)

    listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known
    )
    entry.async_on_unload(coordinator.async_add_listener(listener))
    listener()


class _FurbulousSwitch(FurbulousEntity, SwitchEntity):
    """Switch that uses shared API for commands; state from coordinator."""

    def __init__(
        self,
        coordinator,
        api,
        device_id: int,
        iotid: str,
        *,
        translation_key: str,
        unique_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            device_id,
            translation_key=translation_key,
            unique_id=unique_id,
        )
        self._api = api
        self._iotid = iotid


class FurbulousFullAutoModeSwitch(_FurbulousSwitch):
    """Full auto mode switch."""

    _attr_icon = "mdi:auto-mode"

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="full_auto_mode",
            unique_id=f"{iotid}_full_auto_mode_switch",
        )

    @property
    def is_on(self) -> bool:
        """Return True if full auto mode is on."""
        device = self.device_data
        if not device:
            return False
        return (
            extract_prop_value(
                (device.get("properties") or {}).get("FullAutoModeSwitch")
            )
            == 1
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable full auto mode."""
        if not await self._api.set_device_property(
            self._iotid, {"FullAutoModeSwitch": 1}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable full auto mode."""
        if not await self._api.set_device_property(
            self._iotid, {"FullAutoModeSwitch": 0}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()


class FurbulousDNDSwitch(_FurbulousSwitch):
    """Do Not Disturb switch."""

    _attr_icon = "mdi:moon-waning-crescent"

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="do_not_disturb",
            unique_id=f"{iotid}_dnd_switch",
        )

    @property
    def is_on(self) -> bool:
        """Return True if DND is on."""
        device = self.device_data
        if not device:
            return False
        return device.get("is_disturb", 0) == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable DND."""
        if not await self._api.set_device_disturb(self._iotid, True):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable DND."""
        if not await self._api.set_device_disturb(self._iotid, False):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()


class FurbulousChildLockSwitch(_FurbulousSwitch):
    """Child lock switch."""

    _attr_icon = "mdi:lock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="child_lock",
            unique_id=f"{iotid}_child_lock_switch",
        )

    @property
    def is_on(self) -> bool:
        """Return True if child lock is on."""
        device = self.device_data
        if not device:
            return False
        return (
            extract_prop_value(
                (device.get("properties") or {}).get("childLockOnOff")
            )
            == 1
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable child lock."""
        if not await self._api.set_device_property(
            self._iotid, {"childLockOnOff": 1}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable child lock."""
        if not await self._api.set_device_property(
            self._iotid, {"childLockOnOff": 0}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()
