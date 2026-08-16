"""Diagnostics support for Furbulous (secrets redacted)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_REGION, CONF_TOKEN
from .models import FurbulousRuntimeData

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_TOKEN,
    "password",
    "token",
    "authorization",
    "client_token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime: FurbulousRuntimeData = entry.runtime_data
    api = runtime.api
    coordinator = runtime.coordinator
    presence = runtime.presence_coordinator

    devices = (coordinator.data or {}).get("devices") or []
    device_summaries = []
    for device in devices:
        props = device.get("properties") or {}
        device_summaries.append(
            {
                "id": device.get("id"),
                "iotid_suffix": _suffix(device.get("iotid")),
                "name": device.get("name"),
                "online": device.get("device_online"),
                "property_keys": sorted(props.keys()),
                "has_daily_stats": bool(device.get("daily_stats")),
            }
        )

    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "domain": entry.domain,
                "version": entry.version,
                "data": dict(entry.data),
                "unique_id": entry.unique_id,
            },
            TO_REDACT,
        ),
        "region": {
            "id": api.region_id,
            "experimental": api.region.experimental,
            "base_host": api.region.base_url.split("://")[-1].split(":")[0],
            "iso": api.region.iso,
            "area": api.region.area,
        },
        "coordinators": {
            "normal": {
                "last_update_success": coordinator.last_update_success,
                "update_interval_s": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
            },
            "presence": {
                "last_update_success": presence.last_update_success,
                "update_interval_s": (
                    presence.update_interval.total_seconds()
                    if presence.update_interval
                    else None
                ),
            },
        },
        "devices": device_summaries,
        "known_device_count": len(api.known_devices),
        "pets_count": len((coordinator.data or {}).get("pets") or []),
        "analytics": runtime.analytics.diagnostics_summary(),
    }


def _suffix(value: str | None, keep: int = 4) -> str | None:
    """Return a short non-identifying suffix for opaque IDs."""
    if not value:
        return None
    if len(value) <= keep:
        return "***"
    return f"...{value[-keep:]}"
