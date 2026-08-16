"""Time platform — Screen off / Quiet hours daily start and end (writable)."""
from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FurbulousEntity
from .entity_ids import (
    UID_QUIET_HOURS_END,
    UID_QUIET_HOURS_START,
    UID_SCREEN_OFF_SCHEDULE_END,
    UID_SCREEN_OFF_SCHEDULE_START,
    box_uid,
)
from .helpers import async_add_devices_listener
from .schedule_props import (
    DEFAULT_DND_START_KEY,
    DEFAULT_DND_STOP_KEY,
    DEFAULT_ECO_START_KEY,
    DEFAULT_ECO_STOP_KEY,
    DND_START_KEYS,
    DND_STOP_KEYS,
    ECO_START_KEYS,
    ECO_STOP_KEYS,
    first_prop_time,
    resolve_write_payload,
)

if TYPE_CHECKING:
    from . import FurbulousConfigEntry

PARALLEL_UPDATES = 0

# Default window when the cloud has never returned a schedule value yet
_DEFAULT_SCREEN_OFF_START = time(22, 0)
_DEFAULT_SCREEN_OFF_END = time(7, 0)
_DEFAULT_QUIET_START = time(22, 0)
_DEFAULT_QUIET_END = time(8, 0)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FurbulousConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up schedule time entities; dynamically add for new devices."""
    from .device_entities import time_entities_for_device

    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    api = runtime.api
    known: set = set()

    def build(device: dict) -> list:
        return time_entities_for_device(coordinator, api, device)

    listener = async_add_devices_listener(
        coordinator, async_add_entities, build, known
    )
    entry.async_on_unload(coordinator.async_add_listener(listener))
    listener()


class FurbulousScheduleTime(FurbulousEntity, TimeEntity):
    """Daily start or end time for Screen off or Quiet hours (API write)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator,
        api,
        device_id: int,
        iotid: str,
        *,
        translation_key: str,
        unique_slug: str,
        keys: tuple[str, ...],
        default_key: str,
        default_time: time,
        icon: str,
    ) -> None:
        super().__init__(
            coordinator,
            device_id,
            translation_key=translation_key,
            unique_id=box_uid(device_id, unique_slug),
        )
        self._api = api
        self._iotid = iotid
        self._keys = keys
        self._default_key = default_key
        self._default_time = default_time
        self._attr_icon = icon

    def _props(self) -> dict[str, Any]:
        device = self.device_data or {}
        return device.get("properties") or {}

    @property
    def native_value(self) -> time | None:
        """Current schedule time from properties, or a sensible default."""
        value, _key = first_prop_time(self._props(), self._keys)
        return value if value is not None else self._default_time

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        value, key = first_prop_time(self._props(), self._keys)
        return {
            "property_key": key or self._default_key,
            "from_device": "yes" if value is not None else "no",
            "plain_english": (
                "Daily window for this mode. The switch only works inside "
                "start–end; set both times so the box behaves as expected."
            ),
            "audience": "setting",
        }

    async def async_set_value(self, value: time) -> None:
        """Write schedule time to the cloud API."""
        payload = resolve_write_payload(
            self._props(),
            self._keys,
            self._default_key,
            value,
        )
        if not await self._api.set_device_property(self._iotid, payload):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_property_failed",
            )
        await self.coordinator.async_request_refresh()


def schedule_time_entities(
    coordinator, api, device_id: int, iotid: str
) -> list[FurbulousScheduleTime]:
    """Four schedule times for one box (Screen off + Quiet hours)."""
    return [
        FurbulousScheduleTime(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="screen_off_start",
            unique_slug=UID_SCREEN_OFF_SCHEDULE_START,
            keys=ECO_START_KEYS,
            default_key=DEFAULT_ECO_START_KEY,
            default_time=_DEFAULT_SCREEN_OFF_START,
            icon="mdi:clock-start",
        ),
        FurbulousScheduleTime(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="screen_off_end",
            unique_slug=UID_SCREEN_OFF_SCHEDULE_END,
            keys=ECO_STOP_KEYS,
            default_key=DEFAULT_ECO_STOP_KEY,
            default_time=_DEFAULT_SCREEN_OFF_END,
            icon="mdi:clock-end",
        ),
        FurbulousScheduleTime(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="quiet_hours_start",
            unique_slug=UID_QUIET_HOURS_START,
            keys=DND_START_KEYS,
            default_key=DEFAULT_DND_START_KEY,
            default_time=_DEFAULT_QUIET_START,
            icon="mdi:clock-start",
        ),
        FurbulousScheduleTime(
            coordinator,
            api,
            device_id,
            iotid,
            translation_key="quiet_hours_end",
            unique_slug=UID_QUIET_HOURS_END,
            keys=DND_STOP_KEYS,
            default_key=DEFAULT_DND_STOP_KEY,
            default_time=_DEFAULT_QUIET_END,
            icon="mdi:clock-end",
        ),
    ]
