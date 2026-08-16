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
from .entity_ids import (
    UID_AUTO_CLEAN_AFTER_VISITS,
    UID_CHILD_LOCK,
    UID_EMPTY_CONFIRM_READY,
    UID_QUIET_HOURS,
    UID_SCREEN_OFF,
    box_uid,
)
from .helpers import async_add_devices_listener
from .schedule_props import (
    DND_START_KEYS,
    DND_STOP_KEYS,
    ECO_START_KEYS,
    ECO_STOP_KEYS,
    first_prop,
    schedule_probe_attributes,
)

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
    """Full auto mode — after a visit, clean automatically (no manual start).

    Distinct from Pause/Resume, which only affect an in-progress cycle.
    Configuration entity (settings-style, not daily chore buttons).
    """

    _attr_icon = "mdi:auto-mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="full_auto_mode",
            unique_id=box_uid(device_id, UID_AUTO_CLEAN_AFTER_VISITS),
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

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Clarify vs pause/resume for cat parents + power users."""
        return {
            "plain_english": (
                "ON = box cleans itself after each visit. "
                "OFF = only cleans when you press Clean now."
            ),
            "note": (
                "ON: box starts cleaning after visits automatically. "
                "Pause/Resume only stop or continue a cycle already running."
            ),
            "audience": "setting",
            "vendor_property": "FullAutoModeSwitch",
        }

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
    """Do Not Disturb — quiet hours; stops cleaning runs while active.

    On/off is set via the cloud API. Start/stop schedule times for DND are
    usually set in the Furbulous app; when the API exposes them they appear
    as Eco/DND time sensors under Configuration.
    """

    _attr_icon = "mdi:moon-waning-crescent"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="do_not_disturb",
            unique_id=box_uid(device_id, UID_QUIET_HOURS),
        )

    @property
    def is_on(self) -> bool:
        """Return True if DND is on."""
        device = self.device_data
        if not device:
            return False
        return device.get("is_disturb", 0) == 1

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Point to matching Quiet hours start/end time entities."""
        device = self.device_data or {}
        props = device.get("properties") or {}
        start, start_key = first_prop(props, DND_START_KEYS)
        stop, stop_key = first_prop(props, DND_STOP_KEYS)
        attrs: dict[str, str] = {
            "plain_english": (
                "ON = quiet mode active. The box only respects this inside "
                "Quiet hours start–end (set those times on this device)."
            ),
            "audience": "setting",
        }
        if start:
            attrs["quiet_hours_start"] = start
            if start_key:
                attrs["quiet_hours_start_key"] = start_key
        if stop:
            attrs["quiet_hours_end"] = stop
            if stop_key:
                attrs["quiet_hours_end_key"] = stop_key
        return attrs

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


class FurbulousEnergySavingSwitch(_FurbulousSwitch):
    """Screen off toggle (energy-saving display dim/blank in standby).

    Single control for the display (replaces legacy Screen on/off buttons):
    - ON  = screen off / dimmed (masterSleepOnOff = 1)
    - OFF = screen on / normal (masterSleepOnOff = 0)

    Placed under Configuration with other settings-style switches.
    """

    _attr_icon = "mdi:monitor-off"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="screen_off",
            unique_id=box_uid(device_id, UID_SCREEN_OFF),
        )

    @property
    def is_on(self) -> bool:
        """Return True when the display is in energy-saving / off mode."""
        device = self.device_data
        if not device:
            return False
        return (
            extract_prop_value(
                (device.get("properties") or {}).get("masterSleepOnOff")
            )
            == 1
        )

    @property
    def available(self) -> bool:
        """Available when the property is present on the device."""
        device = self.device_data
        if not device or not self.coordinator.last_update_success:
            return False
        return (device.get("properties") or {}).get("masterSleepOnOff") is not None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Clarify semantics; surface eco schedule if API returns times."""
        device = self.device_data or {}
        props = device.get("properties") or {}
        start, start_key = first_prop(props, ECO_START_KEYS)
        stop, stop_key = first_prop(props, ECO_STOP_KEYS)
        attrs: dict[str, str] = {
            "effect": "display_dim_standby",
            "when_on": "screen_off_or_dimmed",
            "when_off": "screen_on_normal",
            "plain_english": (
                "ON blanks/dims the screen only inside Screen off start–end. "
                "Set those times on this device or the display may stay on."
            ),
            "note": (
                "ON blanks/dims the display. Daily window is Screen off start "
                "and Screen off end (writable time entities)."
            ),
            "audience": "setting",
        }
        if start:
            attrs["eco_start"] = start
            if start_key:
                attrs["eco_start_key"] = start_key
        if stop:
            attrs["eco_stop"] = stop
            if stop_key:
                attrs["eco_stop_key"] = stop_key
        attrs.update(schedule_probe_attributes(props))
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn screen off (energy saving on)."""
        if not await self._api.set_device_property(
            self._iotid, {"masterSleepOnOff": 1}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn screen on (energy saving off)."""
        if not await self._api.set_device_property(
            self._iotid, {"masterSleepOnOff": 0}
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()


class FurbulousEmptyConfirmSwitch(_FurbulousSwitch):
    """Arm Empty for 90s after the user confirms the drum is closed.

    Required before the Empty button will run (safety). Auto-clears after use
    or timeout. Name starts with “Empty” so it sorts next to the Empty button.
    Stays under Controls (chore action, not a settings toggle).
    """

    _attr_icon = "mdi:checkbox-marked-outline"
    # No entity_category → Controls section, next to Empty button alphabetically

    def __init__(self, coordinator, api, device_id: int, iotid: str) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="empty_confirm_ready",
            unique_id=box_uid(device_id, UID_EMPTY_CONFIRM_READY),
        )

    @property
    def is_on(self) -> bool:
        """True while empty is armed."""
        from .empty_safety import is_empty_armed

        return is_empty_armed(self._device_id)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Safety copy for the UI."""
        return {
            "plain_english": (
                "Safety switch. Turn ON only when the drum is closed and you "
                "are ready to dump the litter, then press Empty all litter within 90s."
            ),
            "warning": (
                "Empty all litter dumps everything. The litter drum/globe must be closed. "
                "Turn this ON only when ready, then press Empty all litter within 90 seconds."
            ),
            "audience": "chore",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm Empty for 90 seconds."""
        from .empty_safety import arm_empty

        arm_empty(self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm Empty."""
        from .empty_safety import disarm_empty

        disarm_empty(self._device_id)
        self.async_write_ha_state()


class FurbulousChildLockSwitch(_FurbulousSwitch):
    """Child lock switch (Configuration)."""

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
            unique_id=box_uid(device_id, UID_CHILD_LOCK),
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
