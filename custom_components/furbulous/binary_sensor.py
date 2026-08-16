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
from .entity_ids import (
    UID_CAT_INSIDE,
    UID_CHILD_LOCK_ON,
    UID_COVER_OPEN,
    UID_DRAWER_OUT_OF_PLACE,
    UID_NEEDS_EMPTYING,
    UID_ONLINE,
    UID_SCREEN_IS_OFF,
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
        workstatus = extract_prop_value(
            (device.get("properties") or {}).get("workstatus")
        )
        return workstatus == 1

    def _entity_fingerprint(self) -> object:
        """Fingerprint occupancy only (ignore other property churn)."""
        device = self.device_data
        workstatus = None
        if device:
            workstatus = extract_prop_value(
                (device.get("properties") or {}).get("workstatus")
            )
        return ("occ", workstatus == 1, self.available)


class FurbulousWasteBinFullSensor(FurbulousEntity, BinarySensorEntity):
    """Waste bin status (PROBLEM class: OK when not full, Problem when full).

    Values: **OK** (bin has room) / **Problem** (litter full — empty needed).
    errorReportEvent == 16.
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
        """Return True if litter-full error code is set."""
        device = self.device_data
        if not device:
            return False
        error_code = extract_prop_value(
            (device.get("properties") or {}).get("errorReportEvent")
        )
        return error_code == 16

    @property
    def icon(self) -> str:
        """Dynamic icon based on state."""
        return "mdi:delete-alert" if self.is_on else "mdi:delete-empty"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Explain OK vs Problem for cat parents + power users."""
        return {
            "when_ok": "Bag has room — nothing to do",
            "when_problem": "Time to empty / seal the bag",
            "plain_english": "OK = fine. Problem = needs emptying.",
            "error_code": "16",
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
    """Read-only mirror of Screen off (masterSleepOnOff).

    Prefer the **Screen off** switch for control. Disabled by default so the
    device page does not show a second Screen-off style control.
    """

    _attr_icon = "mdi:lightbulb-night"
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
        """Return True if energy-saving / sleep mode property is on."""
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
        """Available when property exists."""
        device = self.device_data
        if not device or not self.coordinator.last_update_success:
            return False
        return (device.get("properties") or {}).get("masterSleepOnOff") is not None


class FurbulousCoverOpenSensor(FurbulousEntity, BinarySensorEntity):
    """Cover status (PROBLEM: OK when closed, Problem when open). Code 128."""

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
        return (
            extract_prop_value(
                (device.get("properties") or {}).get("errorReportEvent")
            )
            == 128
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {
            "when_ok": "Cover closed — fine",
            "when_problem": "Close the cover",
            "plain_english": "OK = closed. Problem = cover is open.",
            "error_code": "128",
            "vendor_property": "errorReportEvent",
            "audience": "primary",
        }


class FurbulousDrawerNotInPlaceSensor(FurbulousEntity, BinarySensorEntity):
    """Drawer status (PROBLEM: OK when seated, Problem when not). Code 64."""

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
        return (
            extract_prop_value(
                (device.get("properties") or {}).get("errorReportEvent")
            )
            == 64
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {
            "when_ok": "Drawer seated — fine",
            "when_problem": "Push the drawer fully in",
            "plain_english": "OK = drawer in place. Problem = drawer out.",
            "error_code": "64",
            "vendor_property": "errorReportEvent",
            "audience": "primary",
        }
