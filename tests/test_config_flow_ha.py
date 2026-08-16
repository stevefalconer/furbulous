"""Config flow tests using pytest-homeassistant-custom-component.

Skipped automatically when full Home Assistant is not installed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.furbulous.const import CONF_REGION, DOMAIN
from custom_components.furbulous.furbulous_api import (
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry


pytestmark = pytest.mark.asyncio


async def test_user_form_shows(hass: HomeAssistant) -> None:
    """User step form is shown without input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_success_creates_entry(hass: HomeAssistant) -> None:
    """Valid credentials create a config entry with region."""
    with (
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.authenticate",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.get_devices",
            new_callable=AsyncMock,
            return_value=[{"id": 1, "iotid": "x"}],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "secret",
                CONF_REGION: "us",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Furbulous (user@example.com)"
    assert result["data"][CONF_EMAIL] == "user@example.com"
    assert result["data"][CONF_REGION] == "us"
    assert result["result"].unique_id == "user@example.com_us"


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Auth failure shows invalid_auth."""
    with patch(
        "custom_components.furbulous.config_flow.FurbulousCatAPI.authenticate",
        new_callable=AsyncMock,
        side_effect=FurbulousCatAuthError("bad"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "wrong",
                CONF_REGION: "us",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Network failure shows cannot_connect."""
    with patch(
        "custom_components.furbulous.config_flow.FurbulousCatAPI.authenticate",
        new_callable=AsyncMock,
        side_effect=FurbulousCatConnectionError("down"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "secret",
                CONF_REGION: "eu",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Duplicate unique_id aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com_us",
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_REGION: "us",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.authenticate",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.get_devices",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "secret",
                CONF_REGION: "us",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Reauth updates entry and aborts successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com_us",
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "old",
            CONF_REGION: "us",
        },
        title="Furbulous (user@example.com)",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.authenticate",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.get_devices",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=entry.data,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "newpass",
                CONF_REGION: "us",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "newpass"


async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Reconfigure can change region when unique id free."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com_us",
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_REGION: "us",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.authenticate",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.furbulous.config_flow.FurbulousCatAPI.get_devices",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "secret",
                CONF_REGION: "eu",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_REGION] == "eu"
    assert entry.unique_id == "user@example.com_eu"
