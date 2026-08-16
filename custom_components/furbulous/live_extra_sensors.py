"""P0b live API sensors — map fields already in the poll payload (no extra HTTP)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory

from .entity import FurbulousEntity, extract_prop_value
from .schedule_props import (
    DND_START_KEYS,
    DND_STOP_KEYS,
    ECO_START_KEYS,
    ECO_STOP_KEYS,
    first_prop,
)

# Vendor handMode codes → cat-friendly labels (what the box is doing)
_BOX_ACTION_LABELS = {
    0: "Idle",
    1: "Cleaning",
    2: "Emptying",
    3: "Packing bag",
    4: "Paused",
    5: "Resuming",
}

# Best-effort completionStatus labels (vendor enum not fully documented)
_COMPLETION_LABELS = {
    0: "Not complete",
    1: "Complete",
    2: "In progress",
    3: "Failed",
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
    """What the box is doing right now (vendor handMode).

    Formerly labeled “Hand mode” (vendor jargon). Cat-friendly name: Box action.
    Values: Idle, Cleaning, Emptying, Packing bag, Paused, Resuming.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="box_action",
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
        return _BOX_ACTION_LABELS.get(code, str(code))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self.device_data or {}
        raw = extract_prop_value((device.get("properties") or {}).get("handMode"))
        return {
            "plain_english": (
                "Shows Idle, Cleaning, Emptying, Packing bag, Paused, or Resuming."
            ),
            "raw_hand_mode": raw if raw is not None else "-",
            "vendor_property": "handMode",
            "audience": "power",
            "note": (
                "Idle = waiting. Cleaning = cycle running. Emptying / Packing bag "
                "are waste actions. Paused / Resuming control an in-progress cycle."
            ),
            "automation_hint": "Trigger on state change or raw_hand_mode attribute",
        }


class FurbulousCompletionStatusSensor(FurbulousEntity, SensorEntity):
    """Cycle completion status from properties.completionStatus.

    Vendor does not publish a full enum. We map common codes and always expose
    the raw value for automations / diagnostics. Field intent: whether the last
    clean/pack/empty cycle finished successfully (used for “cycle finished”
    automations once values are confirmed on your unit).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="cycle_completion",
            unique_id=f"furbulous_{device_id}_completionStatus",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        raw = extract_prop_value(
            (device.get("properties") or {}).get("completionStatus")
        )
        if raw is None:
            return "-"
        try:
            code = int(raw)
        except (TypeError, ValueError):
            return str(raw)
        return _COMPLETION_LABELS.get(code, f"Code {code}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self.device_data or {}
        raw = extract_prop_value(
            (device.get("properties") or {}).get("completionStatus")
        )
        return {
            "raw_completion_status": raw if raw is not None else "-",
            "note": (
                "Mapped labels are best-effort. Confirm with Download diagnostics "
                "after a clean cycle if automating on this field."
            ),
        }


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


class FurbulousEcoStartSensor(FurbulousEntity, SensorEntity):
    """Eco / screen-off schedule start (daily), when exposed by the API.

    Write schedules remain in the Furbulous app until property keys are confirmed.
    Configuration category so it sits with Screen off / DND settings.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="eco_mode_start",
            unique_id=f"furbulous_{device_id}_eco_mode_start",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        value, _key = first_prop(device.get("properties") or {}, ECO_START_KEYS)
        return value if value else "-"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        device = self.device_data or {}
        value, key = first_prop(device.get("properties") or {}, ECO_START_KEYS)
        return {
            "property_key": key or "-",
            "note": (
                "Daily eco/screen schedule start. Set in the Furbulous app if "
                "this shows “-”. Captured property keys appear after cloud returns them."
            ),
            "has_value": "yes" if value else "no",
        }


class FurbulousEcoStopSensor(FurbulousEntity, SensorEntity):
    """Eco / screen-off schedule stop (daily), when exposed by the API."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="eco_mode_stop",
            unique_id=f"furbulous_{device_id}_eco_mode_stop",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        value, _key = first_prop(device.get("properties") or {}, ECO_STOP_KEYS)
        return value if value else "-"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        device = self.device_data or {}
        value, key = first_prop(device.get("properties") or {}, ECO_STOP_KEYS)
        return {
            "property_key": key or "-",
            "note": (
                "Daily eco/screen schedule stop. Set in the Furbulous app if "
                "this shows “-”. Write from HA needs confirmed API keys."
            ),
            "has_value": "yes" if value else "no",
        }


class FurbulousDndStartSensor(FurbulousEntity, SensorEntity):
    """Do not disturb / night mode schedule start when exposed by the API."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-start"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="dnd_start",
            unique_id=f"furbulous_{device_id}_dnd_start",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        value, _key = first_prop(device.get("properties") or {}, DND_START_KEYS)
        return value if value else "-"


class FurbulousDndStopSensor(FurbulousEntity, SensorEntity):
    """Do not disturb / night mode schedule stop when exposed by the API."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-end"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, device_id: int) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key="dnd_stop",
            unique_id=f"furbulous_{device_id}_dnd_stop",
        )

    @property
    def native_value(self) -> str:
        device = self.device_data
        if not device:
            return "-"
        value, _key = first_prop(device.get("properties") or {}, DND_STOP_KEYS)
        return value if value else "-"
