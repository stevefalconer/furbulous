"""Entity registry helpers — clear sticky display overrides.

Home Assistant stores per-entity unit and name overrides that survive reloads.
Weight is special: HA unit system does **not** auto-convert g→lb (unlike °C/°F).
The weight sensor suggests mass_unit (lb/g); registry must allow that suggestion
to apply via ``sensor.private`` refresh after reconfigure/upgrade.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# User-facing sensor options that lock display unit / precision
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
        clear_custom_names: Remove custom entity names so translation_key applies.
        weight_units_only: Only touch weight sensors' unit options (upgrade path).

    Returns:
        Number of entities updated.
    """
    registry = er.async_get(hass)
    updated = 0

    for entity_entry in er.async_entries_for_config_entry(
        registry, config_entry.entry_id
    ):
        is_weight = _is_weight_entity(entity_entry)
        if weight_units_only and not is_weight:
            continue

        changed = False
        kwargs: dict[str, Any] = {}

        if clear_custom_names and entity_entry.name is not None:
            kwargs["name"] = None
            changed = True

        if entity_entry.has_entity_name is False:
            kwargs["has_entity_name"] = True
            changed = True

        if entity_entry.unit_of_measurement is not None:
            if not weight_units_only or is_weight:
                kwargs["unit_of_measurement"] = None
                changed = True

        if kwargs:
            registry.async_update_entity(entity_entry.entity_id, **kwargs)
            changed = True

        if entity_entry.domain == "sensor":
            # User unit lock under "sensor"
            sensor_opts = dict(entity_entry.options.get("sensor", {}))
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

            # Weight: force HA to re-run initial suggested unit (lb/g from unit system)
            # via sensor.private refresh_initial_entity_options (core sensor path).
            if is_weight:
                registry.async_update_entity_options(
                    entity_entry.entity_id,
                    "sensor.private",
                    {"refresh_initial_entity_options": True},
                )
                changed = True
            elif not weight_units_only and "sensor.private" in entity_entry.options:
                # Non-weight: drop private suggested unit so native unit applies
                registry.async_update_entity_options(
                    entity_entry.entity_id, "sensor.private", None
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
            "(weight will follow HA mass unit: lb or g)",
            updated,
        )
    return updated
