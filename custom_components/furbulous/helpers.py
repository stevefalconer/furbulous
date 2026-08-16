"""Small shared helpers for platform setup (dynamic devices)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

try:
    from homeassistant.core import callback as _ha_callback
except ImportError:  # pragma: no cover - unit test stubs
    def _ha_callback(func):  # type: ignore[misc]
        return func


def async_add_devices_listener(
    coordinator: DataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    build_entities: Callable[[dict[str, Any]], list],
    known_ids: set[Any],
) -> Callable[[], None]:
    """Return a coordinator listener that adds entities for newly seen devices.

    ``build_entities(device)`` returns a list of entities for one device dict.
    ``known_ids`` is mutated as devices are registered (shared per platform).
    """

    @_ha_callback
    def _async_add_new() -> None:
        data = coordinator.data or {}
        new_entities: list = []
        for device in data.get("devices") or []:
            device_id = device.get("id")
            if device_id is None or device_id in known_ids:
                continue
            entities = build_entities(device)
            if entities:
                known_ids.add(device_id)
                new_entities.extend(entities)
        if new_entities:
            async_add_entities(new_entities)

    return _async_add_new
