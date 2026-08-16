"""Entity registry helpers — clear sticky display overrides.

Home Assistant stores per-entity unit and name overrides that survive reloads.
After 1.1.x→1.2.0 or a reconfigure, those can leave weight stuck on g/kg/lb and
hardcoded English (or other) names instead of translation_key + unit system.

Call ``async_clear_display_overrides`` after successful reauth/reconfigure
(before reload) so the next setup uses native grams + current HA language.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensor option keys HA uses for unit conversion / precision overrides
_SENSOR_OPTION_KEYS = (
    "unit_of_measurement",
    "suggested_unit_of_measurement",
    "display_precision",
    "suggested_display_precision",
)

# Unique-id fragments for weight entities (native grams)
_WEIGHT_UNIQUE_MARKERS = ("catWeight", "cat_weight")


def _is_weight_entity(entry: er.RegistryEntry) -> bool:
    """Return True if this registry entry is a Furbulous cat weight sensor."""
    if entry.domain != "sensor":
        return False
    uid = entry.unique_id or ""
    return any(marker in uid for marker in _WEIGHT_UNIQUE_MARKERS)


async def async_clear_display_overrides(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    *,
    clear_custom_names: bool = True,
    weight_units_only: bool = False,
) -> int:
    """Clear sticky unit/name overrides for this config entry's entities.

    Args:
        clear_custom_names: If True, remove user/custom entity names so
            ``translation_key`` + HA language apply again.
        weight_units_only: If True, only clear unit options on weight sensors
            (safer for automatic upgrade path). If False, clear unit overrides
            on all sensors under this entry.

    Returns:
        Number of entities updated.
    """
    registry = er.async_get(hass)
    updated = 0

    for entity_entry in er.async_entries_for_config_entry(
        registry, config_entry.entry_id
    ):
        changed = False
        kwargs: dict[str, Any] = {}

        # --- Custom name (blocks language packs) ---
        if clear_custom_names and entity_entry.name is not None:
            kwargs["name"] = None
            changed = True

        # Ensure has_entity_name so device + translation_key compose correctly
        if entity_entry.has_entity_name is False:
            kwargs["has_entity_name"] = True
            changed = True

        # Clear top-level unit_of_measurement if present (legacy / some paths)
        if entity_entry.unit_of_measurement is not None:
            if not weight_units_only or _is_weight_entity(entity_entry):
                kwargs["unit_of_measurement"] = None
                changed = True

        if kwargs:
            registry.async_update_entity(entity_entry.entity_id, **kwargs)
            changed = True

        # --- Sensor domain options (unit conversion lock) ---
        if entity_entry.domain == "sensor":
            if weight_units_only and not _is_weight_entity(entity_entry):
                if changed:
                    updated += 1
                continue

            sensor_opts = dict(entity_entry.options.get("sensor", {}))
            if not sensor_opts:
                if changed:
                    updated += 1
                continue

            cleaned = {
                key: value
                for key, value in sensor_opts.items()
                if key not in _SENSOR_OPTION_KEYS
            }
            if cleaned != sensor_opts:
                registry.async_update_entity_options(
                    entity_entry.entity_id, "sensor", cleaned
                )
                changed = True

        if changed:
            updated += 1
            _LOGGER.debug(
                "Cleared display overrides for %s (unique_id=%s)",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )

    if updated:
        _LOGGER.info(
            "Cleared display overrides on %s Furbulous entit(y/ies) "
            "(units/names will follow HA unit system and language)",
            updated,
        )
    return updated
