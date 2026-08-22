"""Entry-level (hub) entities: pause cloud polling for the phone app."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .entity_ids import (
    UID_PAUSE_CLOUD_POLLING,
    UID_PAUSE_POLLING,
    UID_PAUSE_POLLING_1H,
    UID_POLLING_PAUSED,
    UID_POLLING_STATUS,
    UID_RESUME_POLLING,
    hub_uid,
)
from .poll_pause import hub_device_info
from .ux import ROLE_SETTING, power_attrs


def _wire_pause_listener(entity: Entity, poll_pause) -> None:
    """Refresh hub entity when pause state changes."""

    @callback
    def _handle() -> None:
        entity.async_write_ha_state()

    entity.async_on_remove(poll_pause.async_add_listener(_handle))


class FurbulousPausePollingSwitch(SwitchEntity):
    """ON = stop all Furbulous cloud polling (indefinite until turned off)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:cloud-off-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, poll_pause) -> None:
        self._entry = entry
        self._poll_pause = poll_pause
        self._attr_translation_key = "pause_cloud_polling"
        self._attr_unique_id = hub_uid(entry.entry_id, UID_PAUSE_CLOUD_POLLING)
        self._attr_device_info = hub_device_info(entry.entry_id, entry.title)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _wire_pause_listener(self, self._poll_pause)

    @property
    def is_on(self) -> bool:
        return self._poll_pause.is_paused

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._poll_pause.async_pause_indefinite()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._poll_pause.async_resume(source="switch")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        until = self._poll_pause.resume_at
        return power_attrs(
            role=ROLE_SETTING,
            automation_hint=(
                "ON stops HA↔Furbulous cloud polls so the phone app can use "
                "the same account. OFF resumes. Prefer Pause 1 hour for short edits."
            ),
            extra={
                "mode": self._poll_pause.mode,
                "resume_at": until.isoformat() if until else None,
                "status": self._poll_pause.status_label,
            },
        )


class FurbulousPausePollingButton(ButtonEntity):
    """Pause cloud polling indefinitely until Resume."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:cloud-off-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, poll_pause) -> None:
        self._entry = entry
        self._poll_pause = poll_pause
        self._attr_translation_key = "pause_polling"
        self._attr_unique_id = hub_uid(entry.entry_id, UID_PAUSE_POLLING)
        self._attr_device_info = hub_device_info(entry.entry_id, entry.title)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _wire_pause_listener(self, self._poll_pause)

    async def async_press(self) -> None:
        await self._poll_pause.async_pause_indefinite()


class FurbulousPausePolling1hButton(ButtonEntity):
    """Pause cloud polling for one hour, then auto-resume."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:timer-pause-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, poll_pause) -> None:
        self._entry = entry
        self._poll_pause = poll_pause
        self._attr_translation_key = "pause_polling_1_hour"
        self._attr_unique_id = hub_uid(entry.entry_id, UID_PAUSE_POLLING_1H)
        self._attr_device_info = hub_device_info(entry.entry_id, entry.title)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _wire_pause_listener(self, self._poll_pause)

    async def async_press(self) -> None:
        await self._poll_pause.async_pause_for()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return power_attrs(
            role=ROLE_SETTING,
            automation_hint=(
                "Pauses for 60 minutes then resumes automatically. "
                "Press Resume polling to resume early."
            ),
        )


class FurbulousResumePollingButton(ButtonEntity):
    """Resume cloud polling after Pause or Pause 1 hour."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:cloud-sync-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, poll_pause) -> None:
        self._entry = entry
        self._poll_pause = poll_pause
        self._attr_translation_key = "resume_polling"
        self._attr_unique_id = hub_uid(entry.entry_id, UID_RESUME_POLLING)
        self._attr_device_info = hub_device_info(entry.entry_id, entry.title)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _wire_pause_listener(self, self._poll_pause)

    async def async_press(self) -> None:
        await self._poll_pause.async_resume(source="button")


class FurbulousPollingStatusSensor(SensorEntity):
    """Human-readable polling state for the dashboard header."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:cloud-sync-outline"

    def __init__(self, entry, poll_pause) -> None:
        self._entry = entry
        self._poll_pause = poll_pause
        self._attr_translation_key = "polling_status"
        self._attr_unique_id = hub_uid(entry.entry_id, UID_POLLING_STATUS)
        self._attr_device_info = hub_device_info(entry.entry_id, entry.title)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _wire_pause_listener(self, self._poll_pause)

    @property
    def native_value(self) -> str:
        return self._poll_pause.status_label

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        until = self._poll_pause.resume_at
        return power_attrs(
            role=ROLE_SETTING,
            automation_hint=(
                "Polling (30s / 5min) | Paused | Paused until HH:MM. "
                "30s = status/actions; 5min = analytics/reporting."
            ),
            extra={
                "mode": self._poll_pause.mode,
                "paused": self._poll_pause.is_paused,
                "resume_at": until.isoformat() if until else None,
                "resume_clock": self._poll_pause.format_resume_clock(),
            },
        )


class FurbulousPollingPausedBinary(BinarySensorEntity):
    """On when cloud polling is paused (intentional — not a fault)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:cloud-off-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, poll_pause) -> None:
        self._entry = entry
        self._poll_pause = poll_pause
        self._attr_translation_key = "polling_paused"
        self._attr_unique_id = hub_uid(entry.entry_id, UID_POLLING_PAUSED)
        self._attr_device_info = hub_device_info(entry.entry_id, entry.title)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _wire_pause_listener(self, self._poll_pause)

    @property
    def is_on(self) -> bool:
        return self._poll_pause.is_paused

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "plain_english": (
                "On = HA is not calling the Furbulous cloud so the phone app "
                "can use this account. Off = normal polling."
            ),
            "mode": self._poll_pause.mode,
            "status": self._poll_pause.status_label,
            "audience": "setting",
        }


def hub_entities_for_entry(entry, poll_pause) -> list[Entity]:
    """All hub entities for one config entry."""
    return [
        FurbulousPausePollingSwitch(entry, poll_pause),
        FurbulousPausePollingButton(entry, poll_pause),
        FurbulousPausePolling1hButton(entry, poll_pause),
        FurbulousResumePollingButton(entry, poll_pause),
        FurbulousPollingStatusSensor(entry, poll_pause),
        FurbulousPollingPausedBinary(entry, poll_pause),
    ]
