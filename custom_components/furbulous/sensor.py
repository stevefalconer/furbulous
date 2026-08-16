"""Sensor platform for Furbulous."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ERROR_CODES
from .entity import FurbulousEntity, extract_prop_value
from .helpers import async_add_devices_listener
from .weight import resolve_cat_weight_grams

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Furbulous sensors; add more when new devices appear."""
    from .device_entities import sensor_entities_for_device

    coordinator = config_entry.runtime_data.coordinator
    known: set = set()

    def build(device: dict) -> list:
        return sensor_entities_for_device(coordinator, device)

    listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known
    )
    config_entry.async_on_unload(coordinator.async_add_listener(listener))
    listener()  # initial devices


class FurbulousLastActivitySensor(FurbulousEntity, SensorEntity):
    """Timestamp of last device activity."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="last_activity",
            unique_id=f"furbulous_{device_id}_last_active",
        )

    @property
    def native_value(self) -> datetime | None:
        """Return last activity as UTC datetime."""
        device = self.device_data
        if not device:
            return None
        timestamp = device.get("active_time")
        if timestamp:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return None


class FurbulousCatWeightSensor(FurbulousEntity, SensorEntity):
    """Cat weight — API native grams; display unit follows HA mass unit system.

    Home Assistant does **not** auto-map weight g→lb from the unit system the way
    it does for temperature. We set ``suggested_unit_of_measurement`` from
    ``hass.config.units.mass_unit`` (lb for US Customary, g for Metric) so the
    first registration and a registry refresh show pounds when the user chose
    imperial mass.
    """

    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:weight"

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="cat_weight",
            unique_id=f"furbulous_{device_id}_catWeight",
        )

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        """Prefer HA mass unit (e.g. lb) when convertible from grams."""
        if self.hass is None:
            return None
        mass_unit = self.hass.config.units.mass_unit
        # Metric profile uses grams as mass_unit — keep native g (return None).
        # US Customary uses pounds — suggest lb so the UI converts from grams.
        if mass_unit and mass_unit != UnitOfMass.GRAMS:
            return mass_unit
        return None

    @property
    def native_value(self) -> float | None:
        """Return weight in grams (API-native)."""
        device = self.device_data
        if not device:
            return None
        return resolve_cat_weight_grams(device.get("properties") or {})

    @property
    def available(self) -> bool:
        """Available when a weight can be resolved."""
        device = self.device_data
        if not device or not self.coordinator.last_update_success:
            return False
        return resolve_cat_weight_grams(device.get("properties") or {}) is not None


class FurbulousDailyUsesSensor(FurbulousEntity, SensorEntity):
    """Daily use count from wcheader stats."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="daily_uses",
            unique_id=f"furbulous_{device_id}_daily_times",
        )

    @property
    def native_value(self) -> int | None:
        """Return daily use count."""
        device = self.device_data
        if not device:
            return None
        stats = device.get("daily_stats") or {}
        value = stats.get("times")
        return int(value) if value is not None else None


class FurbulousAverageDurationSensor(FurbulousEntity, SensorEntity):
    """Average daily duration in seconds."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="average_daily_duration",
            unique_id=f"furbulous_{device_id}_daily_avg_duration",
        )

    @property
    def native_value(self) -> int | None:
        """Return average duration in seconds."""
        device = self.device_data
        if not device:
            return None
        stats = device.get("daily_stats") or {}
        value = stats.get("avg_duration")
        return int(value) if value is not None else None


class FurbulousErrorSensor(FurbulousEntity, SensorEntity):
    """Human-readable error report from device."""

    _attr_icon = "mdi:alert-circle"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="error",
            unique_id=f"furbulous_{device_id}_errorReportEvent",
        )

    @property
    def native_value(self) -> str | None:
        """Return mapped error description."""
        device = self.device_data
        if not device:
            return None
        value = extract_prop_value(
            device.get("properties", {}).get("errorReportEvent")
        )
        if value is None:
            return None
        return ERROR_CODES.get(value, f"Error {value}")

    def _entity_fingerprint(self) -> object:
        """Fingerprint on raw error code (not translated string only)."""
        device = self.device_data
        raw = None
        if device:
            raw = extract_prop_value(
                device.get("properties", {}).get("errorReportEvent")
            )
        return ("err", raw, self.available)

    @property
    def available(self) -> bool:
        """Available when property exists."""
        device = self.device_data
        if not device or not self.coordinator.last_update_success:
            return False
        return device.get("properties", {}).get("errorReportEvent") is not None
