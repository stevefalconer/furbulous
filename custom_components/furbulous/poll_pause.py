"""Pause Furbulous cloud polling so the phone app can use the same account.

HA holds a session against the vendor cloud; pausing both coordinators stops
API traffic without unloading the integration. Timed pause auto-resumes.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    UPDATE_INTERVAL_FAST_SECONDS,
    UPDATE_INTERVAL_NORMAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

PAUSE_1H_SECONDS = 3600
MODE_ACTIVE = "active"
MODE_PAUSED = "paused"
MODE_PAUSED_UNTIL = "paused_until"


class PollPauseController:
    """Entry-scoped pause for the full + presence coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        coordinator: Any,
        presence_coordinator: Any,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.coordinator = coordinator
        self.presence_coordinator = presence_coordinator
        self._paused = False
        self._until: datetime | None = None
        self._unsub_timer: Callable[[], None] | None = None
        self._listeners: list[Callable[[], None]] = []

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Poll pause listener failed")

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def resume_at(self) -> datetime | None:
        """UTC datetime when a timed pause ends; None if indefinite or active."""
        return self._until if self._paused else None

    @property
    def mode(self) -> str:
        if not self._paused:
            return MODE_ACTIVE
        if self._until is not None:
            return MODE_PAUSED_UNTIL
        return MODE_PAUSED

    def format_resume_clock(self) -> str | None:
        """HH:MM in HA local timezone for 'Paused until …'."""
        if not self._paused or self._until is None:
            return None
        local = dt_util.as_local(self._until)
        return f"{local.hour:02d}:{local.minute:02d}"

    @property
    def status_label(self) -> str:
        if not self._paused:
            return "Polling (30s / 5min)"
        if self._until is None:
            return "Paused"
        clock = self.format_resume_clock()
        return f"Paused until {clock}"

    def _cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    def _apply_intervals(self, *, paused: bool) -> None:
        if paused:
            self.coordinator.update_interval = None
            self.presence_coordinator.update_interval = None
        else:
            self.coordinator.update_interval = timedelta(
                minutes=UPDATE_INTERVAL_NORMAL_MINUTES
            )
            self.presence_coordinator.update_interval = timedelta(
                seconds=UPDATE_INTERVAL_FAST_SECONDS
            )

    async def async_pause_indefinite(self) -> None:
        """Stop polling until explicitly resumed."""
        self._cancel_timer()
        self._paused = True
        self._until = None
        self._apply_intervals(paused=True)
        _LOGGER.info("Furbulous cloud polling paused (indefinite) entry=%s", self.entry_id)
        self._notify()

    async def async_pause_for(self, seconds: float = PAUSE_1H_SECONDS) -> None:
        """Stop polling and auto-resume after ``seconds``."""
        seconds = max(60.0, float(seconds))
        self._cancel_timer()
        self._paused = True
        self._until = dt_util.utcnow() + timedelta(seconds=seconds)
        self._apply_intervals(paused=True)

        @callback
        def _fire(_now: datetime) -> None:
            self.hass.async_create_task(self.async_resume(source="timer"))

        self._unsub_timer = async_call_later(self.hass, seconds, _fire)
        _LOGGER.info(
            "Furbulous cloud polling paused for %.0fs (until %s) entry=%s",
            seconds,
            self._until.isoformat(),
            self.entry_id,
        )
        self._notify()

    async def async_resume(self, *, source: str = "user") -> None:
        """Resume normal polling intervals and refresh once."""
        was = self._paused
        self._cancel_timer()
        self._paused = False
        self._until = None
        self._apply_intervals(paused=False)
        if was:
            _LOGGER.info(
                "Furbulous cloud polling resumed (%s) entry=%s",
                source,
                self.entry_id,
            )
            try:
                await self.presence_coordinator.async_request_refresh()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Presence refresh after resume failed", exc_info=True)
            try:
                await self.coordinator.async_request_refresh()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Full refresh after resume failed", exc_info=True)
        self._notify()

    async def async_set_paused(self, paused: bool) -> None:
        """Switch helper: on = indefinite pause, off = resume."""
        if paused:
            await self.async_pause_indefinite()
        else:
            await self.async_resume(source="switch")

    def async_unload(self) -> None:
        """Cancel timers on entry unload (intervals restored by unload)."""
        self._cancel_timer()


def hub_device_info(entry_id: str, title: str | None = None) -> Any:
    """DeviceInfo for entry-level (hub) entities.

    Device name stays ``Furbulous`` so entity_ids are stable
    (``switch.furbulous_pause_cloud_polling``), not email-slugified.
    """
    from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

    return DeviceInfo(
        identifiers={(DOMAIN, f"hub_{entry_id}")},
        name="Furbulous",
        manufacturer="Furbulous",
        model=title or "Home Assistant",
        entry_type=DeviceEntryType.SERVICE,
    )
