"""Shared entity base for Furbulous platforms."""
from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .device import get_device_info


class FurbulousEntity(CoordinatorEntity):
    """Coordinator-backed entity with HA naming and change-gated state writes.

    Uses has_entity_name + translation_key. Device name comes from the device
    registry; entity name is translated. Entities never call the cloud API.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        device_id: int,
        translation_key: str,
        unique_id: str,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_translation_key = translation_key
        self._attr_unique_id = unique_id
        self._last_fingerprint: object | None = object()  # force first write
        device = self.device_data
        if device:
            self._attr_device_info = get_device_info(device)

    @property
    def device_data(self) -> dict | None:
        """Return this entity's device dict from coordinator data."""
        data = self.coordinator.data
        if not data:
            return None
        devices = data.get("devices") or []
        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def available(self) -> bool:
        """Return True if device data is present and last update succeeded."""
        return self.coordinator.last_update_success and self.device_data is not None

    def _entity_fingerprint(self) -> object:
        """Return a hashable fingerprint of the entity's meaningful state.

        Subclasses should override for richer comparison; default uses
        native_value / is_on when present.
        """
        if hasattr(self, "native_value"):
            return ("nv", getattr(self, "native_value"), self.available)
        if hasattr(self, "is_on"):
            return ("on", getattr(self, "is_on"), self.available)
        if hasattr(self, "current_option"):
            return ("opt", getattr(self, "current_option"), self.available)
        return (id(self.coordinator.data), self.available)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write HA state only when the entity's value meaningfully changed."""
        fingerprint = self._entity_fingerprint()
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        super()._handle_coordinator_update()


def extract_prop_value(prop: object) -> Any:
    """Normalize property payloads that may be raw values or {value, time}."""
    if prop is None:
        return None
    if isinstance(prop, dict):
        return prop.get("value")
    return prop
