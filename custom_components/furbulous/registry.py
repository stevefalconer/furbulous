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

# Dashboard expects these entity_ids for pause-polling controls (1.3.15+).
_HUB_DESIRED_ENTITY_IDS: dict[str, str] = {
    "pause_cloud_polling": "switch.furbulous_pause_cloud_polling",
    "pause_polling": "button.furbulous_pause_polling",
    "pause_polling_1_hour": "button.furbulous_pause_polling_1_hour",
    "resume_polling": "button.furbulous_resume_polling",
    "polling_status": "sensor.furbulous_cloud_polling",
    "polling_paused": "binary_sensor.furbulous_cloud_polling_paused",
}

# User-facing sensor options that lock display unit / precision
_SENSOR_OPTION_KEYS = (
    "unit_of_measurement",
    "suggested_unit_of_measurement",
    "display_precision",
    "suggested_display_precision",
)

# Unique-id fragments for weight entities (display lb/kg from API grams)
_WEIGHT_UNIQUE_MARKERS = ("cat_weight", "catWeight")

# Removed controls: screen buttons (1.3.4) and Screen off switch (1.3.9 DisplaySwitch mode)
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


def _is_orphan_screen_control(entry: er.RegistryEntry) -> bool:
    """True for removed Screen on/off buttons or Screen off switch."""
    if entry.domain not in ("button", "switch"):
        return False
    uid = entry.unique_id or ""
    return any(uid.endswith(suffix) for suffix in _ORPHAN_UNIQUE_SUFFIXES)


async def async_ensure_hub_pause_entity_ids(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> int:
    """Force hub pause entities onto stable dashboard entity_ids.

    Early installs sometimes slugified the config-entry title into the device
    name (``Furbulous (email)``), producing unavailable chips on the example
    dashboard that expects ``button.furbulous_pause_polling`` etc.
    """
    from homeassistant.helpers import device_registry as dr

    from .const import DOMAIN

    renamed = 0
    device_reg = dr.async_get(hass)
    hub_ident = (DOMAIN, f"hub_{config_entry.entry_id}")
    device = device_reg.async_get_device(identifiers={hub_ident})
    if device is not None and (
        device.name != "Furbulous" or device.name_by_user not in (None, "Furbulous")
    ):
        device_reg.async_update_device(
            device.id,
            name="Furbulous",
            name_by_user=None,
        )
        _LOGGER.info("Normalized Furbulous hub device name for pause controls")

    registry = er.async_get(hass)
    prefix = f"furbulous_hub_{config_entry.entry_id}_"
    for entity_entry in list(
        er.async_entries_for_config_entry(registry, config_entry.entry_id)
    ):
        uid = entity_entry.unique_id or ""
        if not uid.startswith(prefix):
            continue
        slug = uid[len(prefix) :]
        desired = _HUB_DESIRED_ENTITY_IDS.get(slug)
        if not desired or entity_entry.entity_id == desired:
            continue
        try:
            registry.async_update_entity(
                entity_entry.entity_id, new_entity_id=desired
            )
            renamed += 1
            _LOGGER.info(
                "Renamed hub entity %s → %s",
                entity_entry.entity_id,
                desired,
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Could not rename %s to %s (may already exist)",
                entity_entry.entity_id,
                desired,
                exc_info=True,
            )
    return renamed


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
        if not _is_orphan_screen_control(entity_entry):
            continue
        registry.async_remove(entity_entry.entity_id)
        removed += 1
        _LOGGER.info(
            "Removed orphaned entity %s (unique_id=%s)",
            entity_entry.entity_id,
            entity_entry.unique_id,
        )
    return removed


async def async_purge_config_entry_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> int:
    """Remove all registry entities for this config entry (one-shot ID rewrite).

    Used when unique_id scheme changes before public adoption so HA does not
    leave unavailable orphans alongside the new cat-parent IDs.
    """
    registry = er.async_get(hass)
    removed = 0
    for entity_entry in list(
        er.async_entries_for_config_entry(registry, config_entry.entry_id)
    ):
        registry.async_remove(entity_entry.entity_id)
        removed += 1
    if removed:
        _LOGGER.info(
            "Purged %s Furbulous entit(y/ies) for cat-parent unique_id scheme",
            removed,
        )
    return removed


# Schedule times moved sensor → time platform (same unique_id slugs)
_SCHEDULE_UID_SUFFIXES = (
    "_screen_off_schedule_start",
    "_screen_off_schedule_end",
    "_quiet_hours_start",
    "_quiet_hours_end",
)


async def async_remove_legacy_schedule_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> int:
    """Drop old sensor-domain schedule entities so time platform can own them."""
    registry = er.async_get(hass)
    removed = 0
    for entity_entry in list(
        er.async_entries_for_config_entry(registry, config_entry.entry_id)
    ):
        if entity_entry.domain != "sensor":
            continue
        uid = entity_entry.unique_id or ""
        if not any(uid.endswith(s) for s in _SCHEDULE_UID_SUFFIXES):
            continue
        registry.async_remove(entity_entry.entity_id)
        removed += 1
    if removed:
        _LOGGER.info(
            "Removed %s legacy schedule sensor(s); use time entities instead",
            removed,
        )
    return removed


async def async_enable_all_entry_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> int:
    """Clear disabled_by so previously default-disabled entities appear."""
    registry = er.async_get(hass)
    enabled = 0
    for entity_entry in list(
        er.async_entries_for_config_entry(registry, config_entry.entry_id)
    ):
        if entity_entry.disabled_by is None:
            continue
        registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
        enabled += 1
    if enabled:
        _LOGGER.info(
            "Enabled %s Furbulous entit(y/ies) that were disabled by default",
            enabled,
        )
    return enabled


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
