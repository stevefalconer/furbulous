"""Sensor platform for Furbulous."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FurbulousEntity, extract_prop_value
from .error_report import describe_error, parse_error_code
from .entity_ids import (
    UID_AVERAGE_VISIT_TODAY,
    UID_CAT_WEIGHT,
    UID_DEVICE_LAST_ACTIVE,
    UID_ERROR_MESSAGE,
    UID_USES_TODAY,
    box_uid,
)
from .helpers import async_add_devices_listener
from .weight import (
    preferred_display_mass_unit,
    resolve_cat_weight_for_display,
    resolve_cat_weight_grams,
)

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Furbulous sensors; add more when new devices/pets appear."""
    from .analytics_entities import pet_analytics_entities
    from .device_entities import sensor_entities_for_device

    runtime = config_entry.runtime_data
    coordinator = runtime.coordinator
    presence = runtime.presence_coordinator
    analytics = runtime.analytics
    known_devices: set = set()
    known_pets: set = set()

    def build(device: dict) -> list:
        return sensor_entities_for_device(
            coordinator, presence, analytics, device
        )

    device_listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known_devices
    )

    def _add_devices_and_pets() -> None:
        device_listener()
        data = coordinator.data or {}
        new_pet_entities: list = []
        for pet in data.get("pets") or []:
            pid = pet.get("id")
            key = str(pid) if pid is not None else pet.get("name")
            if key is None or key in known_pets:
                continue
            known_pets.add(key)
            new_pet_entities.extend(
                pet_analytics_entities(coordinator, analytics, pet)
            )
        if new_pet_entities:
            async_add_entities(new_pet_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_add_devices_and_pets)
    )
    _add_devices_and_pets()

    from .hub import FurbulousPollingStatusSensor

    async_add_entities(
        [FurbulousPollingStatusSensor(config_entry, runtime.poll_pause)]
    )


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
            unique_id=box_uid(device_id, UID_DEVICE_LAST_ACTIVE),
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
    """Cat weight — convert API grams to lb (US) or kg (metric) for the state.

    HA unit-system auto-conversion for weight is sticky/unreliable on existing
    entities (unlike temperature). Per product requirement we **calculate** the
    display value from ``hass.config.units.mass_unit``:

    - US Customary (mass lb/oz) → state in **lb**
    - Metric → state in **kg**

    ``native_value`` and ``native_unit_of_measurement`` always match so the UI
    shows the correct number without relying on registry unit conversion.
    """

    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:weight"

    def __init__(self, coordinator, device_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_id,
            translation_key="cat_weight",
            unique_id=box_uid(device_id, UID_CAT_WEIGHT),
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """lb for US Customary, kg for metric (from HA unit system)."""
        return preferred_display_mass_unit(self.hass)

    @property
    def native_value(self) -> float | None:
        """Return weight already converted to native_unit_of_measurement."""
        device = self.device_data
        if not device:
            return None
        value, _unit = resolve_cat_weight_for_display(
            device.get("properties") or {}, self.hass
        )
        return value

    def _entity_fingerprint(self) -> object:
        """Include unit so a unit-system change forces a state write."""
        return (
            "weight",
            self.native_value,
            self.native_unit_of_measurement,
            self.available,
        )

    @property
    def available(self) -> bool:
        """Available when a weight can be resolved from the API."""
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
            unique_id=box_uid(device_id, UID_USES_TODAY),
        )

    @property
    def native_value(self) -> int:
        """Return daily use count (0 before first stats poll)."""
        device = self.device_data
        if not device:
            return 0
        stats = device.get("daily_stats") or {}
        value = stats.get("times")
        return int(value) if value is not None else 0


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
            unique_id=box_uid(device_id, UID_AVERAGE_VISIT_TODAY),
        )

    @property
    def native_value(self) -> int | None:
        """Return average duration in seconds (None → HA shows unknown until data)."""
        device = self.device_data
        if not device:
            return None
        stats = device.get("daily_stats") or {}
        value = stats.get("avg_duration")
        return int(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Explain empty/unknown for duration device class."""
        return {
            "empty_display": "unknown",
            "note": (
                "DURATION sensors cannot use “-” as state. Unknown means no "
                "average yet (or stats not loaded). 0s is a real zero average."
            ),
        }


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
            unique_id=box_uid(device_id, UID_ERROR_MESSAGE),
        )

    @property
    def native_value(self) -> str:
        """Return mapped error description (``-`` / No error when clear)."""
        device = self.device_data
        if not device:
            return "-"
        return describe_error(device.get("properties", {}).get("errorReportEvent"))

    def _entity_fingerprint(self) -> object:
        """Fingerprint on raw error code (not translated string only)."""
        device = self.device_data
        raw = None
        if device:
            raw = parse_error_code(
                device.get("properties", {}).get("errorReportEvent")
            )
        return ("err", raw, self.available)
