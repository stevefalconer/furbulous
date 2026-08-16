"""Binary sensor platform for Furbulous Cat integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FurbulousCatDataUpdateCoordinator
from .const import DOMAIN
from .device import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Furbulous Cat binary sensors."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = coordinators["coordinator"]
    fast_coordinator = coordinators["fast_coordinator"]

    entities = []
    
    # Add binary sensors for each device
    devices = coordinator.data.get("devices", [])
    for device in devices:
        device_id = device.get("id")
        iotid = device.get("iotid")
        
        if iotid:
            entities.extend([
                # 1. Device online status
                FurbulousCatOnlineBinarySensor(coordinator, device_id),
                
                # 2. Cat in box sensor (FAST UPDATE - 30 seconds)
                FurbulousCatInBoxSensor(fast_coordinator, device_id),
                
                # 3. Waste bin full sensor
                FurbulousCatWasteBinFullSensor(coordinator, device_id),
                
                # 4. Child lock (only security binary sensor needed)
                FurbulousCatPropertyBinarySensor(
                    coordinator, device_id, "childLockOnOff", "Child lock", "lock"
                ),
                
                # 5. Sleep mode (Do Not Disturb)
                FurbulousCatPropertyBinarySensor(
                    coordinator, device_id, "masterSleepOnOff", "Sleep mode", "running"
                ),
            ])
    
    async_add_entities(entities)


class FurbulousCatOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for device online status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: FurbulousCatDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"furbulous_{device_id}_connectivity"
        
        # Set device info
        device = self.device_data
        if device:
            self._attr_device_info = get_device_info(device)

    @property
    def device_data(self) -> dict | None:
        """Get the device data from coordinator."""
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device = self.device_data
        if device:
            device_name = device.get("name", f"Device {self._device_id}")
            return f"{device_name} - Connected"
        return f"Furbulous Device {self._device_id} - Connected"

    @property
    def is_on(self) -> bool:
        """Return true if the device is online."""
        device = self.device_data
        if device:
            return device.get("device_online") == 1
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.device_data is not None


class FurbulousCatInBoxSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for cat presence in litter box (FAST UPDATE - 30 seconds)."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: FurbulousCatDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"furbulous_{device_id}_cat_in_box"
        
        # Set device info
        device = self.device_data
        if device:
            self._attr_device_info = get_device_info(device)

    @property
    def device_data(self) -> dict | None:
        """Get the device data from coordinator."""
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device = self.device_data
        if device:
            device_name = device.get("name", f"Device {self._device_id}")
            return f"{device_name} - Cat in litter box"
        return f"Furbulous Device {self._device_id} - Cat in litter box"

    @property
    def is_on(self) -> bool:
        """Return true if cat is in the litter box."""
        device = self.device_data
        if device:
            properties = device.get("properties", {})
            workstatus_prop = properties.get("workstatus")
            
            if workstatus_prop:
                # Handle both dict {"value": x} and direct value cases
                if isinstance(workstatus_prop, dict):
                    workstatus = workstatus_prop.get("value", 0)
                else:
                    workstatus = workstatus_prop
                
                # workstatus == 1 means "Working" = Cat is using the litter box
                # workstatus == 0 means "Idle" = no cat
                # workstatus == 2 means "Cleaning" = cleaning in progress
                return workstatus == 1
        
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        device = self.device_data
        if not device:
            return {}
        
        properties = device.get("properties", {})
        workstatus_prop = properties.get("workstatus")
        
        attrs = {}
        
        if workstatus_prop:
            if isinstance(workstatus_prop, dict):
                workstatus = workstatus_prop.get("value", 0)
                attrs["last_update"] = workstatus_prop.get("time")
            else:
                workstatus = workstatus_prop
            
            # Mapping des statuts
            status_map = {
                0: "Idle",
                1: "Working (Cat present)",
                2: "Cleaning",
                3: "Paused",
                4: "Error",
            }
            attrs["work_status"] = status_map.get(workstatus, f"Unknown ({workstatus})")
            attrs["work_status_code"] = workstatus
        
        # Add cat weight if available
        cat_weight_prop = properties.get("catWeight")
        if cat_weight_prop:
            if isinstance(cat_weight_prop, dict):
                attrs["cat_weight_grams"] = cat_weight_prop.get("value")
            else:
                attrs["cat_weight_grams"] = cat_weight_prop
        
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.device_data is not None


class FurbulousCatWasteBinFullSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for waste bin full status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: FurbulousCatDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_waste_bin_full"
        from .device import get_device_info
        device = self.device_data
        if device:
            self._attr_device_info = get_device_info(device)

    @property
    def device_data(self) -> dict | None:
        """Get the device data from coordinator."""
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device = self.device_data
        if device:
            device_name = device.get("name", f"Device {self._device_id}")
            return f"{device_name} - Waste bin full"
        return f"Furbulous Device {self._device_id} - Waste bin full"

    @property
    def is_on(self) -> bool:
        """Return true if waste bin is full."""
        device = self.device_data
        if device:
            properties = device.get("properties", {})
            
            # Method 1: Check error code 16
            error_prop = properties.get("errorReportEvent")
            if error_prop:
                if isinstance(error_prop, dict):
                    error_code = error_prop.get("value", 0)
                else:
                    error_code = error_prop
                
                if error_code == 16:  # Litter full code
                    return True
            
            # Method 2: Logic based on completionStatus
            # completionStatus == 1 may indicate "done/full"
            completion_prop = properties.get("completionStatus")
            if completion_prop:
                if isinstance(completion_prop, dict):
                    completion = completion_prop.get("value", 0)
                else:
                    completion = completion_prop
                
                # If completionStatus == 0, it may indicate "full"
                # (adjust based on real-world behavior)
                # For now, only rely on this when errorCode == 16
                pass
            
            # Method 3: Check handMode == 2 (dump mode active)
            # If dump mode is active, it may be because the bin is full
            hand_mode_prop = properties.get("handMode")
            if hand_mode_prop:
                if isinstance(hand_mode_prop, dict):
                    hand_mode = hand_mode_prop.get("value", 0)
                else:
                    hand_mode = hand_mode_prop
                
                # handMode == 2 may indicate "needs emptying"
                # (adjust based on behavior)
                pass
        
        return False

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:delete-alert" if self.is_on else "mdi:delete-empty"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        device = self.device_data
        if device:
            properties = device.get("properties", {})
            
            # Extract useful properties
            attrs = {}
            
            # Error code
            error_prop = properties.get("errorReportEvent")
            if error_prop:
                if isinstance(error_prop, dict):
                    error_code = error_prop.get("value", 0)
                else:
                    error_code = error_prop
                attrs["error_code"] = error_code
            
            # Completion status
            completion_prop = properties.get("completionStatus")
            if completion_prop:
                if isinstance(completion_prop, dict):
                    completion = completion_prop.get("value", 0)
                else:
                    completion = completion_prop
                attrs["completion_status"] = completion
            
            # Hand mode
            hand_mode_prop = properties.get("handMode")
            if hand_mode_prop:
                if isinstance(hand_mode_prop, dict):
                    hand_mode = hand_mode_prop.get("value", 0)
                else:
                    hand_mode = hand_mode_prop
                attrs["hand_mode"] = hand_mode
            
            # Usage today
            usage_prop = properties.get("excreteTimesEveryday")
            if usage_prop:
                if isinstance(usage_prop, dict):
                    usage = usage_prop.get("value", 0)
                else:
                    usage = usage_prop
                attrs["usage_today"] = usage
            
            return attrs
        return {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.device_data is not None


class FurbulousCatPropertyBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor based on device properties."""

    def __init__(
        self,
        coordinator: FurbulousCatDataUpdateCoordinator,
        device_id: int,
        property_key: str,
        friendly_name: str,
        device_class: str | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._property_key = property_key
        self._friendly_name = friendly_name
        self._attr_unique_id = f"furbulous_{device_id}_{property_key}_binary"
        
        if device_class:
            self._attr_device_class = device_class
        
        # Set device info
        device = self.device_data
        if device:
            self._attr_device_info = get_device_info(device)

    @property
    def device_data(self) -> dict | None:
        """Get the device data from coordinator."""
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def property_data(self) -> dict | None:
        """Get the property data."""
        device = self.device_data
        if device:
            properties = device.get("properties", {})
            return properties.get(self._property_key)
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device = self.device_data
        if device:
            device_name = device.get("name", f"Device {self._device_id}")
            return f"{device_name} - {self._friendly_name}"
        return f"Furbulous Device {self._device_id} - {self._friendly_name}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        prop = self.property_data
        if prop:
            # Handle both dict {"value": x} and direct value cases
            if isinstance(prop, dict):
                value = prop.get("value")
            else:
                value = prop
            return value == 1
        return False

    @property
    def icon(self) -> str:
        """Return the icon."""
        icons = {
            "FullAutoModeSwitch": "mdi:robot",
            "catCleanOnOff": "mdi:broom",
            "childLockOnOff": "mdi:lock" if self.is_on else "mdi:lock-open",
            "masterSleepOnOff": "mdi:sleep",
            "DisplaySwitch": "mdi:monitor" if self.is_on else "mdi:monitor-off",
            "handMode": "mdi:hand-back-right",
        }
        return icons.get(self._property_key, "mdi:toggle-switch")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.property_data is not None


class FurbulousCatErrorBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for error status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: FurbulousCatDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"furbulous_{device_id}_error"
        
        # Set device info
        device = self.device_data
        if device:
            self._attr_device_info = get_device_info(device)

    @property
    def device_data(self) -> dict | None:
        """Get the device data from coordinator."""
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device = self.device_data
        if device:
            device_name = device.get("name", f"Device {self._device_id}")
            return f"{device_name} - Error"
        return f"Furbulous Device {self._device_id} - Error"

    @property
    def is_on(self) -> bool:
        """Return true if there is an error."""
        device = self.device_data
        if device:
            properties = device.get("properties", {})
            error_prop = properties.get("errorReportEvent")
            if error_prop:
                # Handle both dict {"value": x} and direct value cases
                if isinstance(error_prop, dict):
                    error_code = error_prop.get("value", 0)
                else:
                    error_code = error_prop
                return error_code != 0
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        device = self.device_data
        if device:
            properties = device.get("properties", {})
            error_prop = properties.get("errorReportEvent")
            if error_prop:
                # Handle both dict {"value": x} and direct value cases
                if isinstance(error_prop, dict):
                    error_code = error_prop.get("value", 0)
                else:
                    error_code = error_prop
                return {
                    "error_code": error_code,
                }
        return {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.device_data is not None
