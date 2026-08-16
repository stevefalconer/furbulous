"""Analytics-backed sensors (Layer B) + pet devices."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .analytics.metrics import EMPTY_LABEL, NONE_LABEL
from .const import DOMAIN
from .device import get_device_info
from .entity_ids import (
    UID_AVG_HOURS_BETWEEN_SEALS_30_DAYS,
    UID_AVG_WAIT_UNTIL_EMPTIED_30_DAYS,
    UID_BAG_AGE_HOURS,
    UID_BAG_AVERAGE_LIFE_30_DAYS,
    UID_BAG_LAST_CHANGED,
    UID_BAG_LAST_LIFESPAN,
    UID_BAG_SEALS_30_DAYS,
    UID_BAGS_USED_30_DAYS,
    UID_HOURS_SINCE_BAG_SEAL,
    UID_LAST_BAG_SEAL,
    UID_LAST_CAT,
    UID_LAST_VISIT,
    UID_LAST_VISIT_TIME,
    UID_LAST_VISIT_WEIGHT,
    UID_LAST_WAIT_UNTIL_EMPTIED,
    UID_LITTER_AGE_HOURS,
    UID_LITTER_AVERAGE_INTERVAL_30_DAYS,
    UID_LITTER_LAST_INTERVAL,
    UID_LITTER_LAST_REFILLED,
    UID_LITTER_REFILLS_30_DAYS,
    UID_LONGEST_WAIT_UNTIL_EMPTIED_30_DAYS,
    UID_PET_FAVORITE_BOX,
    UID_PET_LAST_SEEN,
    UID_PET_VISIT_LENGTH_AVG_30_DAYS,
    UID_PET_VISITS_30_DAYS,
    UID_PET_VISITS_7_DAYS,
    UID_TIMES_BAG_FILLED_30_DAYS,
    UID_VISIT_LENGTH_AVG_30_DAYS,
    UID_VISITS_30_DAYS,
    UID_VISITS_7_DAYS,
    UID_VISITS_ON_LAST_BAG,
    UID_VISITS_SINCE_BAG_SEAL,
    UID_WAITING_WITH_FULL_BAG,
    UID_WHO_IS_INSIDE,
    box_uid,
    pet_uid,
)
from .ux import ROLE_CHORE, ROLE_PRIMARY, power_attrs
from .weight import (
    convert_grams_to_unit,
    preferred_display_mass_unit,
)


def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class AnalyticsBoxSensor(CoordinatorEntity, SensorEntity):
    """Sensor driven by AnalyticsEngine metrics for one box."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        analytics,
        device: dict[str, Any],
        *,
        translation_key: str,
        unique_suffix: str,
        metric_key: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
        icon: str | None = None,
        entity_category: EntityCategory | None = None,
        entity_registry_enabled_default: bool = True,
        as_timestamp: bool = False,
        as_hours: bool = False,
        none_when_missing: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._analytics = analytics
        self._device_id = device.get("id")
        self._metric_key = metric_key
        self._as_timestamp = as_timestamp
        self._as_hours = as_hours
        self._none_when_missing = none_when_missing
        self._attr_translation_key = translation_key
        self._attr_unique_id = box_uid(self._device_id, unique_suffix)
        self._attr_device_info = get_device_info(device)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        if icon:
            self._attr_icon = icon
        if entity_category:
            self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._last_fingerprint: object | None = object()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        """Write state only when the metric value changed (Pi recorder-friendly)."""
        fingerprint = (self.native_value, self.available)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    def _raw(self) -> Any:
        return self._analytics.metrics_for_device(self._device_id).get(
            self._metric_key
        )

    @property
    def native_value(self) -> Any:
        raw = self._raw()
        if raw is None:
            # Duration/timestamp/weight must stay None (not "-") for device classes —
            # HA correctly shows "unknown" until a real value exists.
            if (
                self._none_when_missing
                and self._attr_device_class is None
                and not self._as_timestamp
                and not self._as_hours
            ):
                return EMPTY_LABEL
            # Count-style metrics (no device class, measurement): prefer 0 over unknown
            if (
                self._attr_state_class is not None
                and self._attr_device_class is None
                and not self._as_hours
                and not self._as_timestamp
            ):
                return 0
            return None
        if self._as_timestamp:
            return _ts_to_dt(float(raw))
        if self._as_hours:
            return round(float(raw), 2)
        if isinstance(raw, float):
            return round(raw, 1)
        return raw

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self._analytics.metrics_for_device(self._device_id)
        role = ROLE_CHORE
        if self._metric_key.startswith("visits_") or "duration" in self._metric_key:
            role = ROLE_PRIMARY
        attrs = power_attrs(
            role=role,
            metric_key=self._metric_key,
            automation_hint=(
                f"Use state or metric_key={self._metric_key} in templates; "
                f"unique_id stays stable across renames."
            ),
        )
        for key in (
            "avg_duration_sample_count",
            "pack_gap_sample_count",
            "bag_lifetime_sample_count",
            "litter_interval_sample_count",
            "time_to_clear_sample_count",
        ):
            if key in m and m[key] is not None:
                attrs["sample_count"] = m[key]
                break
        return attrs


class OccupyingPetSensor(CoordinatorEntity, SensorEntity):
    """Who is in the box **right now** only.

    Blank (``-``) when unoccupied. Does not show the last visitor after they leave
    — use **Last visitor** for that (better fit for 30s polls).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:cat"

    def __init__(self, presence, analytics, device: dict) -> None:
        super().__init__(presence)
        self._analytics = analytics
        self._device_id = device.get("id")
        self._attr_translation_key = "occupying_pet"
        self._attr_unique_id = box_uid(self._device_id, UID_WHO_IS_INSIDE)
        self._attr_device_info = get_device_info(device)
        self._last_fingerprint: object | None = object()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )
        # Also refresh on presence coordinator (occupancy changes)
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        fingerprint = (self.native_value, self.available)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        # Empty when no cat in box; name or "-" if occupied but unidentified
        return self._analytics.occupying_pet(self._device_id)


class LastVisitorSensor(CoordinatorEntity, SensorEntity):
    """Last visitor name after a use (``-`` if none yet).

    State changes (including pet names) appear in the device Activity/Logbook.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:paw"

    def __init__(self, coordinator, analytics, device: dict) -> None:
        super().__init__(coordinator)
        self._analytics = analytics
        self._device_id = device.get("id")
        self._attr_translation_key = "last_visitor"
        self._attr_unique_id = box_uid(self._device_id, UID_LAST_CAT)
        self._attr_device_info = get_device_info(device)
        self._last_fingerprint: object | None = object()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        fingerprint = (self.native_value, self.available)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        name = self._analytics.last_visitor(self._device_id)
        return name if name else EMPTY_LABEL

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """How identity was chosen (closest weight like the app)."""
        st = self._analytics._device_state.get(str(self._device_id), {})  # noqa: SLF001
        attrs = power_attrs(
            role=ROLE_PRIMARY,
            automation_hint=(
                "Prefer event furbulous_visit_ended for automations; "
                "state is the cat name (or “-”)."
            ),
            extra={
                "match_method": st.get("last_match_method") or "-",
                "confidence": st.get("last_match_confidence") or "-",
            },
        )
        if st.get("last_visit_weight_g") is not None:
            attrs["visit_weight_g"] = st["last_visit_weight_g"]
        if st.get("last_match_delta_g") is not None:
            attrs["weight_delta_g"] = st["last_match_delta_g"]
        if st.get("last_visitor_id") is not None:
            attrs["pet_id"] = st["last_visitor_id"]
        return attrs


class LastVisitActivitySensor(CoordinatorEntity, SensorEntity):
    """Combined last-visit line for Activity/Logbook: “Fluffy · 2026-08-15 14:32”.

    Prefer this over raw Last activity (device active_time) when you care about
    which cat used the box.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:history"

    def __init__(self, coordinator, analytics, device: dict) -> None:
        super().__init__(coordinator)
        self._analytics = analytics
        self._device_id = device.get("id")
        self._attr_translation_key = "last_visit_activity"
        self._attr_unique_id = box_uid(self._device_id, UID_LAST_VISIT)
        self._attr_device_info = get_device_info(device)
        self._last_fingerprint: object | None = object()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        fingerprint = (self.native_value, self.available)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        name = self._analytics.last_visitor(self._device_id) or EMPTY_LABEL
        ts = self._analytics.last_visit_ts(self._device_id)
        dt_val = _ts_to_dt(ts)
        if dt_val is None and (not name or name == EMPTY_LABEL):
            return EMPTY_LABEL
        time_str = EMPTY_LABEL
        if dt_val is not None:
            try:
                from homeassistant.util import dt as dt_util

                time_str = dt_util.as_local(dt_val).strftime("%Y-%m-%d %H:%M")
            except Exception:  # pylint: disable=broad-except
                time_str = dt_val.strftime("%Y-%m-%d %H:%M UTC")
        if name and name != EMPTY_LABEL:
            if time_str != EMPTY_LABEL:
                return f"{name} · {time_str}"
            return str(name)
        return time_str


class LastVisitTimeSensor(CoordinatorEntity, SensorEntity):
    """When the last visit ended, as HA local time string (or ``-``).

    Uses a text state so the default can be ``-`` (TIMESTAMP would show
    ``unknown`` before the first visit).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, analytics, device: dict) -> None:
        super().__init__(coordinator)
        self._analytics = analytics
        self._device_id = device.get("id")
        self._attr_translation_key = "last_visit_time"
        self._attr_unique_id = box_uid(self._device_id, UID_LAST_VISIT_TIME)
        self._attr_device_info = get_device_info(device)
        self._last_fingerprint: object | None = object()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        fingerprint = (self.native_value, self.available)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        ts = self._analytics.last_visit_ts(self._device_id)
        dt_val = _ts_to_dt(ts)
        if dt_val is None:
            return EMPTY_LABEL
        # Prefer HA local timezone when available
        try:
            from homeassistant.util import dt as dt_util

            local = dt_util.as_local(dt_val)
            return local.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:  # pylint: disable=broad-except
            return dt_val.strftime("%Y-%m-%d %H:%M:%S UTC")


class LastVisitWeightSensor(CoordinatorEntity, SensorEntity):
    """Weight from the last completed visit (lb/kg from HA unit system)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:weight-kilogram"

    def __init__(self, coordinator, analytics, device: dict) -> None:
        super().__init__(coordinator)
        self._analytics = analytics
        self._device_id = device.get("id")
        self._attr_translation_key = "last_visit_weight"
        self._attr_unique_id = box_uid(self._device_id, UID_LAST_VISIT_WEIGHT)
        self._attr_device_info = get_device_info(device)
        self._last_fingerprint: object | None = object()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        fingerprint = (
            self.native_value,
            self.native_unit_of_measurement,
            self.available,
        )
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self) -> str:
        return preferred_display_mass_unit(self.hass)

    @property
    def native_value(self) -> float | None:
        grams = self._analytics.last_visit_weight_g(self._device_id)
        if grams is None:
            return None
        unit = preferred_display_mass_unit(self.hass)
        return convert_grams_to_unit(grams, unit)


class PetDeviceSensor(CoordinatorEntity, SensorEntity):
    """Sensor attached to a pet device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        analytics,
        pet: dict[str, Any],
        *,
        translation_key: str,
        unique_suffix: str,
        metric_key: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        icon: str | None = None,
        as_timestamp: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._analytics = analytics
        self._pet = pet
        self._metric_key = metric_key
        self._as_timestamp = as_timestamp
        pid = pet.get("id")
        self._pet_key = str(pid) if pid is not None else (pet.get("name") or "unknown")
        self._attr_translation_key = translation_key
        self._attr_unique_id = pet_uid(self._pet_key, unique_suffix)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"pet_{self._pet_key}")},
            name=pet.get("name") or EMPTY_LABEL,
            manufacturer="Furbulous",
            model="Pet",
            configuration_url="https://app.furbulouspet.com",
        )
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if icon:
            self._attr_icon = icon
        self._last_fingerprint: object | None = object()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._analytics.async_add_listener(self._handle_analytics)
        )

    @callback
    def _handle_analytics(self) -> None:
        fingerprint = (self.native_value, self.available)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.async_write_ha_state()

    def _metrics(self) -> dict[str, Any]:
        return self._analytics.pet_metrics.get(self._pet_key, {})

    @property
    def native_value(self) -> Any:
        raw = self._metrics().get(self._metric_key)
        if raw is None:
            return None
        if self._as_timestamp:
            return _ts_to_dt(float(raw))
        if isinstance(raw, float):
            return round(raw, 1)
        return raw


def box_analytics_entities(
    coordinator, presence, analytics, device: dict
) -> list[Entity]:
    """All Layer B sensors for one litter box."""
    did = device.get("id")
    if did is None:
        return []

    def _s(**kwargs) -> AnalyticsBoxSensor:
        return AnalyticsBoxSensor(coordinator, analytics, device, **kwargs)

    entities: list[Entity] = [
        # Last-visit set is primary UX (30s polls can miss live occupancy).
        # Last visit activity includes pet names for the Activity/Logbook section.
        OccupyingPetSensor(presence, analytics, device),
        LastVisitorSensor(coordinator, analytics, device),
        LastVisitActivitySensor(coordinator, analytics, device),
        LastVisitTimeSensor(coordinator, analytics, device),
        LastVisitWeightSensor(coordinator, analytics, device),
        # Names use 7d/30d prefixes so period averages group alphabetically.
        # Secondary gauges disabled-by-default (HA Gold / Pi recorder).
        _s(
            translation_key="visits_30_days",
            unique_suffix=UID_VISITS_30_DAYS,
            metric_key="visits_30d",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:counter",
        ),
        _s(
            translation_key="visits_7_days",
            unique_suffix=UID_VISITS_7_DAYS,
            metric_key="visits_7d",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:counter",
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="avg_visit_duration_30d",
            unique_suffix=UID_VISIT_LENGTH_AVG_30_DAYS,
            metric_key="avg_duration_s_30d",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            icon="mdi:timer-outline",
            none_when_missing=True,
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="time_full_current",
            unique_suffix=UID_WAITING_WITH_FULL_BAG,
            metric_key="current_time_full_s",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            icon="mdi:timer-alert",
        ),
        _s(
            translation_key="last_time_to_clear",
            unique_suffix=UID_LAST_WAIT_UNTIL_EMPTIED,
            metric_key="last_time_to_clear_s",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            icon="mdi:timer-check",
            none_when_missing=True,
        ),
        _s(
            translation_key="avg_time_to_clear_30d",
            unique_suffix=UID_AVG_WAIT_UNTIL_EMPTIED_30_DAYS,
            metric_key="avg_time_to_clear_s_30d",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            none_when_missing=True,
        ),
        _s(
            translation_key="max_time_to_clear_30d",
            unique_suffix=UID_LONGEST_WAIT_UNTIL_EMPTIED_30_DAYS,
            metric_key="max_time_to_clear_s_30d",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            entity_registry_enabled_default=False,
            none_when_missing=True,
        ),
        _s(
            translation_key="full_episodes_30d",
            unique_suffix=UID_TIMES_BAG_FILLED_30_DAYS,
            metric_key="full_episodes_30d",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:counter",
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="last_pack",
            unique_suffix=UID_LAST_BAG_SEAL,
            metric_key="last_pack_ts",
            device_class=SensorDeviceClass.TIMESTAMP,
            as_timestamp=True,
            icon="mdi:package-variant",
        ),
        _s(
            translation_key="hours_since_last_pack",
            unique_suffix=UID_HOURS_SINCE_BAG_SEAL,
            metric_key="hours_since_pack",
            unit="h",
            as_hours=True,
            icon="mdi:clock-outline",
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="avg_hours_between_packs_30d",
            unique_suffix=UID_AVG_HOURS_BETWEEN_SEALS_30_DAYS,
            metric_key="avg_hours_between_packs_30d",
            unit="h",
            as_hours=True,
            none_when_missing=True,
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="packs_30d",
            unique_suffix=UID_BAG_SEALS_30_DAYS,
            metric_key="packs_30d",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:package-variant-closed",
        ),
        _s(
            translation_key="visits_since_last_pack",
            unique_suffix=UID_VISITS_SINCE_BAG_SEAL,
            metric_key="visits_since_last_pack",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:paw",
        ),
        _s(
            translation_key="last_bag_replaced",
            unique_suffix=UID_BAG_LAST_CHANGED,
            metric_key="last_bag_replaced_ts",
            device_class=SensorDeviceClass.TIMESTAMP,
            as_timestamp=True,
            icon="mdi:delete-restore",
        ),
        _s(
            translation_key="hours_since_bag_replaced",
            unique_suffix=UID_BAG_AGE_HOURS,
            metric_key="hours_since_bag_replaced",
            unit="h",
            as_hours=True,
        ),
        _s(
            translation_key="last_bag_lifetime",
            unique_suffix=UID_BAG_LAST_LIFESPAN,
            metric_key="last_bag_lifetime_s",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            none_when_missing=True,
        ),
        _s(
            translation_key="avg_bag_lifetime_30d",
            unique_suffix=UID_BAG_AVERAGE_LIFE_30_DAYS,
            metric_key="avg_bag_lifetime_s_30d",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            none_when_missing=True,
        ),
        _s(
            translation_key="bags_replaced_30d",
            unique_suffix=UID_BAGS_USED_30_DAYS,
            metric_key="bags_replaced_30d",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:counter",
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="visits_during_last_bag",
            unique_suffix=UID_VISITS_ON_LAST_BAG,
            metric_key="visits_during_last_bag",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:paw",
            entity_registry_enabled_default=False,
        ),
        _s(
            translation_key="last_litter_reset",
            unique_suffix=UID_LITTER_LAST_REFILLED,
            metric_key="last_litter_reset_ts",
            device_class=SensorDeviceClass.TIMESTAMP,
            as_timestamp=True,
            icon="mdi:shovel",
        ),
        _s(
            translation_key="hours_since_litter_reset",
            unique_suffix=UID_LITTER_AGE_HOURS,
            metric_key="hours_since_litter_reset",
            unit="h",
            as_hours=True,
        ),
        _s(
            translation_key="last_litter_interval",
            unique_suffix=UID_LITTER_LAST_INTERVAL,
            metric_key="last_litter_interval_s",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            none_when_missing=True,
        ),
        _s(
            translation_key="avg_litter_interval_30d",
            unique_suffix=UID_LITTER_AVERAGE_INTERVAL_30_DAYS,
            metric_key="avg_litter_interval_s_30d",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            none_when_missing=True,
        ),
        _s(
            translation_key="litter_resets_30d",
            unique_suffix=UID_LITTER_REFILLS_30_DAYS,
            metric_key="litter_resets_30d",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:counter",
            entity_registry_enabled_default=False,
        ),
    ]
    return entities


def pet_analytics_entities(coordinator, analytics, pet: dict) -> list[Entity]:
    """Sensors for one pet."""
    return [
        PetDeviceSensor(
            coordinator,
            analytics,
            pet,
            translation_key="pet_visits_7d",
            unique_suffix=UID_PET_VISITS_7_DAYS,
            metric_key="visits_7d",
            icon="mdi:counter",
        ),
        PetDeviceSensor(
            coordinator,
            analytics,
            pet,
            translation_key="pet_visits_30d",
            unique_suffix=UID_PET_VISITS_30_DAYS,
            metric_key="visits_30d",
            icon="mdi:counter",
        ),
        PetDeviceSensor(
            coordinator,
            analytics,
            pet,
            translation_key="pet_avg_duration_30d",
            unique_suffix=UID_PET_VISIT_LENGTH_AVG_30_DAYS,
            metric_key="avg_duration_s_30d",
            device_class=SensorDeviceClass.DURATION,
            unit=UnitOfTime.SECONDS,
            icon="mdi:timer-outline",
        ),
        PetDeviceSensor(
            coordinator,
            analytics,
            pet,
            translation_key="favorite_litter_box",
            unique_suffix=UID_PET_FAVORITE_BOX,
            metric_key="favorite_box",
            icon="mdi:home-heart",
        ),
        PetDeviceSensor(
            coordinator,
            analytics,
            pet,
            translation_key="pet_last_seen",
            unique_suffix=UID_PET_LAST_SEEN,
            metric_key="last_seen_ts",
            device_class=SensorDeviceClass.TIMESTAMP,
            as_timestamp=True,
            icon="mdi:eye",
        ),
    ]
