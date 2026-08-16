"""Config flow for Furbulous."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCOUNT_TYPE,
    CONF_REGION,
    CONFIG_VERSION,
    DEFAULT_ACCOUNT_TYPE,
    DOMAIN,
)
from .furbulous_api import (
    FurbulousCatAPI,
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)
from .regions import REGION_IDS, default_region_for_hass
from .registry import async_clear_display_overrides

_LOGGER = logging.getLogger(__name__)


def _auth_schema(
    *,
    default_email: str | None = None,
    default_region: str | None = None,
    include_defaults: bool = False,
) -> vol.Schema:
    """Build email/password/region schema."""
    if include_defaults and default_region and default_region in REGION_IDS:
        region_field: Any = vol.Required(CONF_REGION, default=default_region)
    elif default_region and default_region in REGION_IDS:
        region_field = vol.Required(CONF_REGION, default=default_region)
    else:
        region_field = vol.Required(CONF_REGION)

    email_field: Any
    if default_email is not None:
        email_field = vol.Required(CONF_EMAIL, default=default_email)
    else:
        email_field = vol.Required(CONF_EMAIL)

    return vol.Schema(
        {
            email_field: TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD, autocomplete="current-password"
                )
            ),
            region_field: SelectSelector(
                SelectSelectorConfig(
                    options=REGION_IDS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="region",
                )
            ),
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Furbulous."""

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._reconfigure_entry: config_entries.ConfigEntry | None = None

    async def _async_validate(
        self, email: str, password: str, region: str, account_type: int = 1
    ) -> dict[str, str]:
        """Validate credentials against the cloud; return errors dict."""
        session = async_get_clientsession(self.hass)
        api = FurbulousCatAPI(
            email=email,
            password=password,
            region_id=region,
            account_type=account_type,
            session=session,
        )
        try:
            await api.authenticate()
            await api.get_devices()
        except FurbulousCatAuthError:
            return {"base": "invalid_auth"}
        except FurbulousCatConnectionError:
            return {"base": "cannot_connect"}
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error during Furbulous validation")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        default_region = default_region_for_hass(self.hass)

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            region = user_input[CONF_REGION]
            errors = await self._async_validate(email, password, region)
            if not errors:
                unique_id = f"{email.lower()}_{region}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Furbulous ({email})",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_REGION: region,
                        CONF_ACCOUNT_TYPE: DEFAULT_ACCOUNT_TYPE,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_auth_schema(default_region=default_region),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth when credentials or region fail at runtime."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication with updated credentials/region."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        assert entry is not None

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            region = user_input[CONF_REGION]
            errors = await self._async_validate(
                email,
                password,
                region,
                account_type=entry.data.get(CONF_ACCOUNT_TYPE, DEFAULT_ACCOUNT_TYPE),
            )
            if not errors:
                unique_id = f"{email.lower()}_{region}"
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_REGION: region,
                    },
                    unique_id=unique_id,
                    title=f"Furbulous ({email})",
                )
                # Drop sticky g/kg/lb and custom names before reload
                await async_clear_display_overrides(
                    self.hass, entry, clear_custom_names=True
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_auth_schema(
                default_email=entry.data.get(CONF_EMAIL, ""),
                default_region=entry.data.get(CONF_REGION, "us"),
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow changing email/password/region without removing the entry."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        self._reconfigure_entry = entry
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            region = user_input[CONF_REGION]
            errors = await self._async_validate(
                email,
                password,
                region,
                account_type=entry.data.get(CONF_ACCOUNT_TYPE, DEFAULT_ACCOUNT_TYPE),
            )
            if not errors:
                unique_id = f"{email.lower()}_{region}"
                for other in self._async_current_entries():
                    if (
                        other.unique_id == unique_id
                        and other.entry_id != entry.entry_id
                    ):
                        return self.async_abort(reason="already_configured")
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_REGION: region,
                    },
                    unique_id=unique_id,
                    title=f"Furbulous ({email})",
                )
                # Ensure prior unit locks / old hardcoded names do not stick
                await async_clear_display_overrides(
                    self.hass, entry, clear_custom_names=True
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_auth_schema(
                default_email=entry.data.get(CONF_EMAIL, ""),
                default_region=entry.data.get(CONF_REGION, "us"),
            ),
            errors=errors,
        )
