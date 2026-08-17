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
    box_uid,
)
from .helpers import apply_write_to_runtime, async_add_devices_listener
from .schedule_props import (
    DND_START_KEYS,
    DND_STOP_KEYS,
    first_prop,
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

    async def _async_set_items(
        self,
        items: dict[str, Any],
        extra_device_fields: dict[str, Any] | None = None,
    ) -> None:
        """Write properties and update local snapshots (no immediate GET)."""
        if not await self._api.set_device_property(self._iotid, items):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        apply_write_to_runtime(
            self.coordinator, self._iotid, items, extra_device_fields
        )


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
        await self._async_set_items({"FullAutoModeSwitch": 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable full auto mode."""
        await self._async_set_items({"FullAutoModeSwitch": 0})


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
        apply_write_to_runtime(
            self.coordinator, self._iotid, {}, extra_device_fields={"is_disturb": 1}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable DND."""
        if not await self._api.set_device_disturb(self._iotid, False):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        apply_write_to_runtime(
            self.coordinator, self._iotid, {}, extra_device_fields={"is_disturb": 0}
        )


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
        await self._async_set_items({"childLockOnOff": 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable child lock."""
        await self._async_set_items({"childLockOnOff": 0})
