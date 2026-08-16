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
    CONF_DISPLAY_RESET_DONE,
    CONF_REGION,
    CONFIG_VERSION,
    DEFAULT_ACCOUNT_TYPE,
    DOMAIN,
)
from .coordinator import FurbulousDataUpdateCoordinator, FurbulousPresenceCoordinator
from .furbulous_api import (
    FurbulousCatAPI,
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)
from .models import FurbulousRuntimeData
from .registry import async_clear_display_overrides

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

    coordinator = FurbulousDataUpdateCoordinator(hass, api, entry)
    presence_coordinator = FurbulousPresenceCoordinator(hass, api, entry)

    await coordinator.async_config_entry_first_refresh()
    await presence_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = FurbulousRuntimeData(
        api=api,
        coordinator=coordinator,
        presence_coordinator=presence_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # One-shot after upgrade from 1.1.x: drop sticky weight unit locks only
    # (does not wipe custom entity names the user intentionally set).
    if not entry.data.get(CONF_DISPLAY_RESET_DONE):
        await async_clear_display_overrides(
            hass,
            entry,
            clear_custom_names=False,
            weight_units_only=True,
        )
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DISPLAY_RESET_DONE: True},
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FurbulousConfigEntry) -> bool:
    """Unload a config entry (shared aiohttp session is not closed)."""
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
