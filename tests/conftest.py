"""Shared pytest fixtures.

When full Home Assistant is installed (pytest-homeassistant-custom-component),
use real HA. Otherwise install lightweight stubs for pure unit tests.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ha_is_real() -> bool:
    try:
        import homeassistant

        return bool(getattr(homeassistant, "__file__", None))
    except ImportError:
        return False


HAS_REAL_HA = _ha_is_real()


def _ensure_module(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    module = ModuleType(name)
    sys.modules[name] = module
    if "." in name:
        parent_name, attr = name.rsplit(".", 1)
        parent = _ensure_module(parent_name)
        setattr(parent, attr, module)
    return module


def _install_homeassistant_stubs() -> None:
    """Minimal stubs so pure unit tests run without Home Assistant."""
    if HAS_REAL_HA:
        return

    ha = _ensure_module("homeassistant")
    ha.__path__ = []

    config_entries = _ensure_module("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    config_entries.ConfigFlow = type("ConfigFlow", (), {"VERSION": 1})

    const = _ensure_module("homeassistant.const")
    const.CONF_EMAIL = "email"
    const.CONF_PASSWORD = "password"
    const.Platform = MagicMock()
    const.UnitOfMass = MagicMock()
    const.UnitOfMass.KILOGRAMS = "kg"
    const.UnitOfMass.GRAMS = "g"
    const.UnitOfTime = MagicMock()
    const.UnitOfTime.SECONDS = "s"
    const.EntityCategory = MagicMock()
    const.EntityCategory.DIAGNOSTIC = "diagnostic"
    const.EntityCategory.CONFIG = "config"

    core = _ensure_module("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    core.callback = lambda f: f

    exceptions = _ensure_module("homeassistant.exceptions")
    exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
    exceptions.ConfigEntryNotReady = type("ConfigEntryNotReady", (Exception,), {})
    exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
    exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})

    def_mod = _ensure_module("homeassistant.data_entry_flow")
    def_mod.FlowResult = dict

    helpers = _ensure_module("homeassistant.helpers")
    helpers.__path__ = []
    aiohttp_client = _ensure_module("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = MagicMock()

    def _coord_init(self, *a, **k):
        self.hass = a[0] if a else k.get("hass")
        self.config_entry = k.get("config_entry")
        self.data = None
        self.last_update_success = True
        self.update_interval = k.get("update_interval")

    update_coordinator = _ensure_module("homeassistant.helpers.update_coordinator")
    update_coordinator.DataUpdateCoordinator = type(
        "DataUpdateCoordinator",
        (),
        {
            "__init__": _coord_init,
            "async_config_entry_first_refresh": MagicMock(),
            "async_request_refresh": MagicMock(),
            "async_add_listener": MagicMock(return_value=lambda: None),
        },
    )
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})
    update_coordinator.CoordinatorEntity = type("CoordinatorEntity", (), {})

    entity_helpers = _ensure_module("homeassistant.helpers.entity")
    entity_helpers.DeviceInfo = dict
    entity_helpers.EntityCategory = MagicMock()
    entity_helpers.Entity = type("Entity", (), {})

    entity_platform = _ensure_module("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = Any

    selector = _ensure_module("homeassistant.helpers.selector")
    selector.SelectSelector = MagicMock
    selector.SelectSelectorConfig = MagicMock
    selector.SelectSelectorMode = MagicMock()
    selector.TextSelector = MagicMock
    selector.TextSelectorConfig = MagicMock
    selector.TextSelectorType = MagicMock()

    device_registry = _ensure_module("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict
    device_registry.async_get = MagicMock()
    device_registry.async_entries_for_config_entry = MagicMock(return_value=[])

    diagnostics = _ensure_module("homeassistant.components.diagnostics")
    diagnostics.async_redact_data = lambda data, keys: data

    for name in (
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.components.binary_sensor",
        "homeassistant.components.button",
        "homeassistant.components.switch",
        "homeassistant.components.select",
    ):
        mod = _ensure_module(name)
        if name.endswith("sensor") and "binary" not in name:
            mod.SensorEntity = type("SensorEntity", (), {})
            mod.SensorDeviceClass = MagicMock()
            mod.SensorDeviceClass.WEIGHT = "weight"
            mod.SensorDeviceClass.DURATION = "duration"
            mod.SensorDeviceClass.TIMESTAMP = "timestamp"
            mod.SensorStateClass = MagicMock()
            mod.SensorStateClass.MEASUREMENT = "measurement"
        if name.endswith("binary_sensor"):
            mod.BinarySensorEntity = type("BinarySensorEntity", (), {})
            mod.BinarySensorDeviceClass = MagicMock()
            mod.BinarySensorDeviceClass.CONNECTIVITY = "connectivity"
            mod.BinarySensorDeviceClass.OCCUPANCY = "occupancy"
            mod.BinarySensorDeviceClass.PROBLEM = "problem"
        if name.endswith("button"):
            mod.ButtonEntity = type("ButtonEntity", (), {})
        if name.endswith("switch"):
            mod.SwitchEntity = type("SwitchEntity", (), {})
        if name.endswith("select"):
            mod.SelectEntity = type("SelectEntity", (), {})


_install_homeassistant_stubs()

US_BASE = "https://app.api.us.furbulouspet.com:1443"


@pytest.fixture
def us_base() -> str:
    return US_BASE


@pytest.fixture
def sample_auth_success() -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": {"token": "test-token-abc123", "identityid": "identity-99"},
    }


@pytest.fixture
def sample_auth_failure() -> dict:
    return {
        "code": 10001,
        "message": "invalid account or password",
        "data": None,
    }


@pytest.fixture
def sample_device_list() -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": 42,
                "iotid": "iot-device-001",
                "name": "Living Room Box",
                "device_online": 1,
                "product_name": "Furbulous Box",
                "active_time": 1700000000,
            }
        ],
    }


@pytest.fixture
def sample_properties_grams() -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": {
            "catWeight": {"value": 4500, "time": 1700000000000},
            "workstatus": {"value": 0, "time": 1700000000000},
            "errorReportEvent": {"value": 0, "time": 1700000000000},
            "FullAutoModeSwitch": {"value": 1, "time": 1700000000000},
            "childLockOnOff": {"value": 0, "time": 1700000000000},
            "catCleanOnOff": {"value": 5, "time": 1700000000000},
        },
    }


@pytest.fixture
def sample_daily_stats() -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": {
            "times": 7,
            "avg_duration": 42,
            "times_diff": 1,
            "avg_diff": -3,
        },
    }


@pytest.fixture
def sample_pets() -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": {"list": [{"id": 1, "name": "Mochi"}]},
    }


# --- Full HA fixtures (only when real HA is present) ---

if HAS_REAL_HA:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable loading of custom_components for every HA test."""
        yield
