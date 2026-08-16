"""The Furbulous integration (cloud polling, Pi-friendly)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCOUNT_TYPE,
    CONF_CAT_UID_SCHEME_V1_DONE,
    CONF_DISPLAY_RESET_DONE,
    CONF_ENABLE_ALL_ENTITIES_DONE,
    CONF_REGION,
    CONF_WEIGHT_CALC_UNIT_RESET_DONE,
    CONFIG_VERSION,
    DEFAULT_ACCOUNT_TYPE,
    DOMAIN,
)
from .analytics.engine import AnalyticsEngine
from .coordinator import FurbulousDataUpdateCoordinator, FurbulousPresenceCoordinator
from .furbulous_api import (
    FurbulousCatAPI,
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)
from .models import FurbulousRuntimeData
from .registry import (
    async_clear_display_overrides,
    async_enable_all_entry_entities,
    async_purge_config_entry_entities,
    async_remove_legacy_schedule_sensors,
    async_remove_orphan_entities,
)

if TYPE_CHECKING:
    FurbulousConfigEntry = ConfigEntry[FurbulousRuntimeData]
else:
    FurbulousConfigEntry = ConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: FurbulousConfigEntry) -> bool:
    """Set up Furbulous from a config entry."""
    region = entry.data.get(CONF_REGION, "us")
    session = async_get_clientsession(hass)
    api = FurbulousCatAPI(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        region_id=region,
        account_type=entry.data.get(CONF_ACCOUNT_TYPE, DEFAULT_ACCOUNT_TYPE),
        session=session,
    )

    try:
        await api.authenticate()
    except FurbulousCatAuthError as err:
        raise ConfigEntryAuthFailed(
            "Invalid credentials or wrong Furbulous region"
        ) from err
    except FurbulousCatConnectionError as err:
        raise ConfigEntryNotReady(
            f"Cannot reach Furbulous cloud: {err}"
        ) from err

    analytics = AnalyticsEngine(hass, entry.entry_id)
    await analytics.async_setup()

    coordinator = FurbulousDataUpdateCoordinator(hass, api, entry)
    presence_coordinator = FurbulousPresenceCoordinator(hass, api, entry)

    # runtime_data before first refresh so coordinators can feed analytics
    entry.runtime_data = FurbulousRuntimeData(
        api=api,
        coordinator=coordinator,
        presence_coordinator=presence_coordinator,
        analytics=analytics,
    )

    await coordinator.async_config_entry_first_refresh()
    await presence_coordinator.async_config_entry_first_refresh()

    # One-shot before platforms: rewrite unique_ids to cat-parent scheme (1.3.7)
    data = dict(entry.data)
    if not data.get(CONF_CAT_UID_SCHEME_V1_DONE):
        await async_purge_config_entry_entities(hass, entry)
        data[CONF_CAT_UID_SCHEME_V1_DONE] = True
        hass.config_entries.async_update_entry(entry, data=data)

    # Drop old sensor-domain schedule entities before time platform registers
    await async_remove_legacy_schedule_sensors(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Drop legacy Screen on/off buttons (1.3.4+) so only Screen off switch remains
    await async_remove_orphan_entities(hass, entry)

    # One-shot: enable entities that were created disabled-by-default earlier
    data = dict(entry.data)
    if not data.get(CONF_ENABLE_ALL_ENTITIES_DONE):
        await async_enable_all_entry_entities(hass, entry)
        data[CONF_ENABLE_ALL_ENTITIES_DONE] = True
        hass.config_entries.async_update_entry(entry, data=data)

    # One-shot after upgrade from 1.1.x: drop sticky weight unit locks only
    # (does not wipe custom entity names the user intentionally set).
    data = dict(entry.data)
    if not data.get(CONF_DISPLAY_RESET_DONE):
        await async_clear_display_overrides(
            hass,
            entry,
            clear_custom_names=False,
            weight_units_only=True,
        )
        data[CONF_DISPLAY_RESET_DONE] = True
        hass.config_entries.async_update_entry(entry, data=data)

    # 1.2.2+: weight is calculated as lb/kg native — clear leftover g locks so
    # entity registry does not fight the new native unit.
    if not data.get(CONF_WEIGHT_CALC_UNIT_RESET_DONE):
        await async_clear_display_overrides(
            hass,
            entry,
            clear_custom_names=False,
            weight_units_only=True,
        )
        data[CONF_WEIGHT_CALC_UNIT_RESET_DONE] = True
        hass.config_entries.async_update_entry(entry, data=data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FurbulousConfigEntry) -> bool:
    """Unload a config entry (flush analytics; shared aiohttp session stays open)."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is not None:
        try:
            eng = runtime.analytics
            for task in (eng._flush_task, eng._delayed_flush_task):  # noqa: SLF001
                if task is not None and not task.done():
                    task.cancel()
            await eng.async_flush(force=True)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.debug("Analytics flush on unload failed", exc_info=True)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate older config entries to the current version."""
    _LOGGER.debug(
        "Migrating Furbulous entry from version %s", config_entry.version
    )

    if config_entry.version > CONFIG_VERSION:
        _LOGGER.error(
            "Config entry version %s is newer than supported %s",
            config_entry.version,
            CONFIG_VERSION,
        )
        return False

    data = {**config_entry.data}

    if config_entry.version < 2:
        region = data.get(CONF_REGION, "us")
        data[CONF_REGION] = region
        email = data.get(CONF_EMAIL, "")
        unique_id = (
            f"{str(email).lower()}_{region}" if email else config_entry.unique_id
        )
        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            unique_id=unique_id,
            version=2,
        )
        _LOGGER.info(
            "Migrated Furbulous config entry to version 2 (region=%s)", region
        )

    return True
