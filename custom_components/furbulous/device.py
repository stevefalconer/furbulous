"""Device registry helpers for Furbulous."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def get_device_info(device_data: dict) -> DeviceInfo:
    """Return DeviceInfo for a Furbulous litter box."""
    device_id = str(device_data.get("id"))
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_data.get("name") or f"Furbulous {device_id}",
        manufacturer="Furbulous",
        model=device_data.get("product_name") or "Furbulous Box",
        sw_version=device_data.get("version"),
        configuration_url="https://app.furbulouspet.com",
    )
