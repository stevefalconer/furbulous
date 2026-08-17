"""Binary sensor platform for Furbulous."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FurbulousEntity, extract_prop_value
from .error_report import (
    is_cover_open,
    is_drawer_out,
    is_trash_door_blocked,
    is_waste_full,
    parse_error_code,
)
from .entity_ids import (
    UID_CAT_INSIDE,
    UID_CHILD_LOCK_ON,
    UID_COVER_OPEN,
    UID_DRAWER_OUT_OF_PLACE,
    UID_NEEDS_EMPTYING,
    UID_ONLINE,
    UID_SCREEN_IS_OFF,
    UID_TRASH_DOOR_BLOCKED,
    box_uid,
)
from .helpers import async_add_devices_listener

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors; dynamically add for new devices."""
    from .device_entities import binary_sensor_entities_for_device

    runtime = config_entry.runtime_data
    coordinator = runtime.coordinator
    presence = runtime.presence_coordinator
    known: set = set()

    def build(device: dict) -> list:
        return binary_sensor_entities_for_device(coordinator, presence, device)

    listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known
    )
    config_entry.async_on_unload(coordinator.async_add_listener(listener))
    listener()


class FurbulousConnectedSensor(FurbulousEntity, BinarySensorEntity):
    """Device online / connectivity."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="connected",
            unique_id=box_uid(device_id, UID_ONLINE),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the device is online."""
        device = self.device_data
        return bool(device and device.get("device_online") == 1)


class FurbulousCatInBoxSensor(FurbulousEntity, BinarySensorEntity):
    """Cat occupancy — fed only by the 30s presence coordinator."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="cat_in_litter_box",
            unique_id=box_uid(device_id, UID_CAT_INSIDE),
        )

    @property
    def is_on(self) -> bool:
        """Return True when workstatus indicates cat present."""
        device = self.device_data
        if not device:
            return False
        from .helpers import is_cat_present

        return is_cat_present(device.get("properties") or {})

    def _entity_fingerprint(self) -> object:
        """Fingerprint occupancy only (ignore other property churn)."""
        from .helpers import is_cat_present

        device = self.device_data
        occupied = is_cat_present((device or {}).get("properties") or {})
        return ("occ", occupied, self.available)


class FurbulousWasteBinFullSensor(FurbulousEntity, BinarySensorEntity):
    """Waste bin status (PROBLEM class: OK when not full, Problem when full).

    Values: **OK** (bin has room) / **Problem** (litter full — empty needed).
    errorReportEvent bit 16 (documented) or 32 (live-verified on zvb-114).
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:delete-empty"

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="waste_bin_status",
            unique_id=box_uid(device_id, UID_NEEDS_EMPTYING),
        )

    @property
    def is_on(self) -> bool:
        """Return True if a litter-full error bit is set."""
        device = self.device_data
        if not device:
            return False
        return is_waste_full((device.get("properties") or {}).get("errorReportEvent"))

    @property
    def icon(self) -> str:
        """Dynamic icon based on state."""
        return "mdi:delete-alert" if self.is_on else "mdi:delete-empty"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Explain OK vs Problem for cat parents + power users."""
        device = self.device_data or {}
        raw = parse_error_code(
            (device.get("properties") or {}).get("errorReportEvent")
        )
        return {
            "when_ok": "Bag has room — nothing to do",
            "when_problem": "Time to empty / seal the bag",
            "plain_english": "OK = fine. Problem = needs emptying.",
            "error_code": str(raw) if raw is not None else "-",
            "full_bits": "16 or 32",
            "vendor_property": "errorReportEvent",
            "audience": "primary",
            "automation_hint": "Also fires furbulous_waste_full / furbulous_waste_cleared",
        }


class FurbulousChildLockBinarySensor(FurbulousEntity, BinarySensorEntity):
    """Child lock status (is_on = lock engaged)."""

    _attr_icon = "mdi:lock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="child_lock",
            unique_id=box_uid(device_id, UID_CHILD_LOCK_ON),
        )

    @property
    def is_on(self) -> bool:
        """Return True if child lock is enabled."""
        device = self.device_data
        if not device:
            return False
        return (
            extract_prop_value(
                (device.get("properties") or {}).get("childLockOnOff")
            )
            == 1
        )

    @property
    def icon(self) -> str:
        """Lock icon."""
        return "mdi:lock" if self.is_on else "mdi:lock-open"

    @property
    def available(self) -> bool:
        """Available when property exists."""
        device = self.device_data
        if not device or not self.coordinator.last_update_success:
            return False
        return (device.get("properties") or {}).get("childLockOnOff") is not None


class FurbulousSleepModeSensor(FurbulousEntity, BinarySensorEntity):
    """Whether the panel should be blank now (DisplaySwitch + schedule).

    Physically verified: DisplaySwitch=0 → lit; DisplaySwitch=1 → blank inside
    displayStartTime–displayEndTime. Not masterSleepOnOff.
    """

    _attr_icon = "mdi:monitor-off"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="energy_saving_active",
            unique_id=box_uid(device_id, UID_SCREEN_IS_OFF),
        )

    @property
    def is_on(self) -> bool:
        """True when the display is expected blank."""
        from .schedule_props import is_display_blanked

        device = self.device_data
        if not device:
            return False
        return is_display_blanked(device.get("properties") or {}, self.hass)

    @property
    def available(self) -> bool:
        """Available when DisplaySwitch is present."""
        device = self.device_data
        if not device or not self.coordinator.last_update_success:
            return False
        return (device.get("properties") or {}).get("DisplaySwitch") is not None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        device = self.device_data or {}
        props = device.get("properties") or {}
        return {
            "DisplaySwitch": str(props.get("DisplaySwitch")),
            "displayStartTime": str(props.get("displayStartTime")),
            "displayEndTime": str(props.get("displayEndTime")),
            "note": (
                "on = Eco/Scheduled says blank now (inside start–end, "
                "house-local). Not live pixels; a button still wakes the panel."
            ),
        }


class FurbulousCoverOpenSensor(FurbulousEntity, BinarySensorEntity):
    """Cover / lid status (PROBLEM). Live lid-off is bit 512; 128 documented."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="cover_status",
            unique_id=box_uid(device_id, UID_COVER_OPEN),
        )

    @property
    def is_on(self) -> bool:
        device = self.device_data
        if not device:
            return False
        return is_cover_open((device.get("properties") or {}).get("errorReportEvent"))

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {
            "when_ok": "Cover closed — fine",
            "when_problem": "Put the lid / cover back on",
            "plain_english": "OK = closed. Problem = lid or cover is off.",
            "error_code": "128 or 512",
            "vendor_property": "errorReportEvent",
            "audience": "primary",
        }


class FurbulousDrawerNotInPlaceSensor(FurbulousEntity, BinarySensorEntity):
    """Drawer status. Cloud does not report drawer-out (live pull stayed 0)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:tray-alert"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="drawer_status",
            unique_id=box_uid(device_id, UID_DRAWER_OUT_OF_PLACE),
        )

    @property
    def is_on(self) -> bool:
        device = self.device_data
        if not device:
            return False
        return is_drawer_out((device.get("properties") or {}).get("errorReportEvent"))

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {
            "when_ok": "Cloud does not report drawer-out — stay OK",
            "when_problem": "Not used (no verified drawer bit)",
            "plain_english": (
                "The box does not tell the cloud when the drawer is out. "
                "Look at the box. Trash-door jam is a different error."
            ),
            "error_code": "none",
            "vendor_property": "errorReportEvent",
            "audience": "primary",
        }


class FurbulousTrashDoorSensor(FurbulousEntity, BinarySensorEntity):
    """Trash-door jam / Device Failure E4 (bit 524288)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:gate-alert"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="trash_door_blocked",
            unique_id=box_uid(device_id, UID_TRASH_DOOR_BLOCKED),
        )

    @property
    def is_on(self) -> bool:
        device = self.device_data
        if not device:
            return False
        return is_trash_door_blocked(
            (device.get("properties") or {}).get("errorReportEvent")
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        device = self.device_data or {}
        raw = parse_error_code(
            (device.get("properties") or {}).get("errorReportEvent")
        )
        return {
            "when_ok": "Trash door can open",
            "when_problem": "Clear the trash lid and press OK on the box",
            "plain_english": "Problem = the waste door could not open (E4).",
            "error_code": str(raw) if raw is not None else "-",
            "vendor_property": "errorReportEvent",
            "audience": "primary",
        }
