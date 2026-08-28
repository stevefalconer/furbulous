"""Small shared helpers for platform setup (dynamic devices)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


def apply_local_properties(
    coordinator: Any,
    iotid: str,
    items: dict[str, Any],
    extra_device_fields: dict[str, Any] | None = None,
) -> bool:
    """Patch a coordinator snapshot after a successful cloud write.

    A GET immediately after properties/set can still return the old value.
    Updating local data keeps switches/selects from snapping back.
    """
    data = getattr(coordinator, "data", None)
    if not isinstance(data, dict) or not iotid:
        return False
    devices = data.get("devices") or []
    new_devices: list[dict[str, Any]] = []
    changed = False
    for device in devices:
        if not isinstance(device, dict) or device.get("iotid") != iotid:
            new_devices.append(device)
            continue
        updated = dict(device)
        props = dict(updated.get("properties") or {})
        for key, value in items.items():
            existing = props.get(key)
            if isinstance(existing, dict):
                wrapped = dict(existing)
                wrapped["value"] = value
                props[key] = wrapped
            else:
                props[key] = value
        updated["properties"] = props
        if extra_device_fields:
            updated.update(extra_device_fields)
        new_devices.append(updated)
        changed = True
    if not changed:
        return False
    new_data = {**data, "devices": new_devices}
    coordinator.data = new_data
    setter = getattr(coordinator, "async_set_updated_data", None)
    if callable(setter):
        setter(new_data)
    return True


def apply_write_to_runtime(
    coordinator: Any,
    iotid: str,
    items: dict[str, Any],
    extra_device_fields: dict[str, Any] | None = None,
) -> None:
    """Patch the writing coordinator and the sibling full/presence snapshot."""
    apply_local_properties(coordinator, iotid, items, extra_device_fields)
    entry = getattr(coordinator, "config_entry", None)
    runtime = getattr(entry, "runtime_data", None) if entry is not None else None
    if runtime is None:
        return
    for other in (
        getattr(runtime, "coordinator", None),
        getattr(runtime, "presence_coordinator", None),
    ):
        if other is not None and other is not coordinator:
            apply_local_properties(other, iotid, items, extra_device_fields)

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


def is_cat_present(properties: dict[str, Any] | None) -> bool:
    """True when the shared classifier says a cat is in the globe."""
    from .box_state import classify

    return classify(properties).cat_present


def _device_row_from_coordinator(
    coordinator: Any,
    device_id: int | str,
    iotid: str | None = None,
) -> dict[str, Any] | None:
    """Return the device dict for id/iotid from a coordinator snapshot, if any."""
    data = getattr(coordinator, "data", None)
    if not isinstance(data, dict):
        return None
    want = str(device_id)
    for device in data.get("devices") or []:
        if not isinstance(device, dict):
            continue
        if str(device.get("id")) == want:
            return device
        if iotid and device.get("iotid") == iotid:
            return device
    return None


def live_error_presence_first(
    presence: Any | None,
    full: Any | None,
    device_id: int | str,
    iotid: str | None = None,
) -> int:
    """Parse ``errorReportEvent`` from presence props first, else full.

    Raises ``HomeAssistantError`` with ``resume_polling_required`` when neither
    snapshot has a usable properties map for the device (paused / empty).
    """
    from homeassistant.exceptions import HomeAssistantError

    from .const import DOMAIN
    from .error_report import parse_error_code

    row = _device_row_from_coordinator(presence, device_id, iotid)
    if row is None:
        row = _device_row_from_coordinator(full, device_id, iotid)
    props = row.get("properties") if isinstance(row, dict) else None
    if not isinstance(props, dict) or not props:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="resume_polling_required",
        )
    code = parse_error_code(props.get("errorReportEvent"))
    return 0 if code is None else code
