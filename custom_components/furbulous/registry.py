"""Entity registry helpers — clear sticky display overrides + prune orphans.

Home Assistant stores per-entity unit and name overrides that survive reloads.
Cat weight is calculated in lb (US) or kg (metric) as the sensor native unit.
Clearing registry unit locks lets that native unit show without a stale ``g``
override from older versions (suggested-unit path).
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

# Unique-id fragments for weight entities (display lb/kg from API grams)
_WEIGHT_UNIQUE_MARKERS = ("catWeight", "cat_weight")

# Removed in 1.3.4+ (replaced by Screen off switch); prune so UI has no dupes
_ORPHAN_UNIQUE_SUFFIXES = (
    "_screen_on",
    "_screen_off",
)


def _is_weight_entity(entry: er.RegistryEntry) -> bool:
    """Return True if this registry entry is a Furbulous cat weight sensor."""
    if entry.domain != "sensor":
        return False
    uid = entry.unique_id or ""
    return any(marker in uid for marker in _WEIGHT_UNIQUE_MARKERS)


def _is_orphan_screen_button(entry: er.RegistryEntry) -> bool:
    """True for legacy Screen on/off *buttons* removed in 1.3.4+."""
    if entry.domain != "button":
        return False
    uid = entry.unique_id or ""
    return any(uid.endswith(suffix) for suffix in _ORPHAN_UNIQUE_SUFFIXES)


async def async_remove_orphan_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> int:
    """Remove registry entries for entities no longer created by the integration.

    Keeps the device page free of duplicate Screen off buttons after upgrade.
    """
    registry = er.async_get(hass)
    removed = 0
    for entity_entry in list(
        er.async_entries_for_config_entry(registry, config_entry.entry_id)
    ):
        if not _is_orphan_screen_button(entity_entry):
            continue
        registry.async_remove(entity_entry.entity_id)
        removed += 1
        _LOGGER.info(
            "Removed orphaned entity %s (unique_id=%s)",
            entity_entry.entity_id,
            entity_entry.unique_id,
        )
    return removed


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

            # Drop private suggested-unit locks so calculated lb/kg native shows.
            if is_weight or (
                not weight_units_only and "sensor.private" in entity_entry.options
            ):
                if "sensor.private" in entity_entry.options or is_weight:
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
            "(cat weight uses calculated lb/kg from HA unit system)",
            updated,
        )
    return updated
