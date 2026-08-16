"""P0b live API sensors — map fields already in the poll payload (no extra HTTP)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory

from .entity import FurbulousEntity, extract_prop_value

_HAND_MODE_LABELS = {
    0: "idle",
    1: "clean",
    2: "empty",
    3: "pack",
    4: "pause",
    5: "resume",
}


class FurbulousFirmwareSensor(FurbulousEntity, SensorEntity):
    """Firmware / software version from device list."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="firmware",
            unique_id=f"furbulous_{device_id}_firmware",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        return device.get("version") or "-"


class FurbulousHandModeSensor(FurbulousEntity, SensorEntity):
    """Current handMode (what the box is doing)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="hand_mode",
            unique_id=f"furbulous_{device_id}_handMode",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        raw = extract_prop_value((device.get("properties") or {}).get("handMode"))
        if raw is None:
            return "-"
        try:
            code = int(raw)
        except (TypeError, ValueError):
            return str(raw)
        return _HAND_MODE_LABELS.get(code, str(code))


class FurbulousCompletionStatusSensor(FurbulousEntity, SensorEntity):
    """Cycle completion status from properties."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="completion_status",
            unique_id=f"furbulous_{device_id}_completionStatus",
        )

    @property
    def native_value(self) -> Any:
        device = self.device_data
        if not device:
            return "-"
        raw = extract_prop_value(
            (device.get("properties") or {}).get("completionStatus")
        )
        return "-" if raw is None else raw


class FurbulousUsesVsYesterdaySensor(FurbulousEntity, SensorEntity):
    """Day-over-day uses delta from wcheader (already fetched)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="uses_vs_yesterday",
            unique_id=f"furbulous_{device_id}_times_diff",
        )

    @property
    def native_value(self) -> int | None:
        device = self.device_data
        if not device:
            return None
        stats = device.get("daily_stats") or {}
        value = stats.get("times_diff")
        return int(value) if value is not None else None


class FurbulousDurationVsYesterdaySensor(FurbulousEntity, SensorEntity):
    """Day-over-day avg duration delta from wcheader."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-timeline-variant"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="duration_vs_yesterday",
            unique_id=f"furbulous_{device_id}_avg_diff",
        )

    @property
    def native_value(self) -> int | None:
        device = self.device_data
        if not device:
            return None
        stats = device.get("daily_stats") or {}
        value = stats.get("avg_diff")
        return int(value) if value is not None else None
