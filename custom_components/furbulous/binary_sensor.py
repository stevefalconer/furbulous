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
            unique_id=f"furbulous_{device_id}_connectivity",
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
            unique_id=f"furbulous_{device_id}_cat_in_box",
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
    """Waste bin full (problem)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:delete-empty"

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="waste_bin_full",
            unique_id=f"{device_id}_waste_bin_full",
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
            unique_id=f"furbulous_{device_id}_childLockOnOff_binary",
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
    """Sleep / master sleep mode."""

    _attr_icon = "mdi:sleep"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="sleep_mode",
            unique_id=f"furbulous_{device_id}_masterSleepOnOff_binary",
        )

    @property
    def is_on(self) -> bool:
        """Return True if sleep mode is on."""
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
