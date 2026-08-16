"""Append-only event store (HA Store, 90-day prune, Pi-safe)."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.analytics"
RETENTION_SECONDS = 90 * 24 * 3600
MAX_EVENTS = 50_000  # hard cap for Pi safety


class EventStore:
    """Persist analytics events per config entry.

    Keeps a flat list for serialization plus a device index for O(k) queries
    instead of scanning the full log on every rollup.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._store: Store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{entry_id}",
        )
        self._events: list[dict[str, Any]] = []
        self._by_device: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._loaded = False

    @property
    def events(self) -> list[dict[str, Any]]:
        """All in-memory events (newest last)."""
        return self._events

    @property
    def event_count(self) -> int:
        """Number of retained events."""
        return len(self._events)

    @property
    def device_ids(self) -> set[str]:
        """Device ids that have at least one stored event."""
        return set(self._by_device.keys())

    async def async_load(self) -> None:
        """Load events from disk once."""
        if self._loaded:
            return
        data = await self._store.async_load()
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            self._events = [e for e in data["events"] if isinstance(e, dict)]
        self._rebuild_index()
        self._loaded = True
        self._prune_in_memory()
        _LOGGER.debug(
            "Analytics store loaded entry=%s events=%s",
            self._entry_id,
            len(self._events),
        )

    async def async_save(self) -> None:
        """Persist current events (call when dirty; prefer debounced flush)."""
        await self._store.async_save({"events": self._events})

    def append(
        self,
        event_type: str,
        *,
        device_id: str | int | None = None,
        iotid: str | None = None,
        source: str = "inferred",
        payload: dict[str, Any] | None = None,
        ts: float | None = None,
    ) -> dict[str, Any]:
        """Append one event (in memory). Caller may batch-save."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "ts": float(ts if ts is not None else time.time()),
            "device_id": str(device_id) if device_id is not None else None,
            "iotid": iotid,
            "source": source,
            "payload": payload or {},
        }
        self._events.append(event)
        did = event.get("device_id")
        if did:
            self._by_device[did].append(event)
        self._prune_in_memory()
        return event

    def events_for_device(
        self,
        device_id: str | int,
        event_types: set[str] | None = None,
        since_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        """Filter events for one device (uses device index)."""
        did = str(device_id)
        out: list[dict[str, Any]] = []
        for ev in self._by_device.get(did, ()):
            if event_types and ev.get("event_type") not in event_types:
                continue
            if since_ts is not None and float(ev.get("ts", 0)) < since_ts:
                continue
            out.append(ev)
        return out

    def events_all(
        self,
        event_types: set[str] | None = None,
        since_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        """Filter events across devices."""
        out: list[dict[str, Any]] = []
        for ev in self._events:
            if event_types and ev.get("event_type") not in event_types:
                continue
            if since_ts is not None and float(ev.get("ts", 0)) < since_ts:
                continue
            out.append(ev)
        return out

    def _rebuild_index(self) -> None:
        self._by_device = defaultdict(list)
        for ev in self._events:
            did = ev.get("device_id")
            if did:
                self._by_device[str(did)].append(ev)

    def _prune_in_memory(self) -> None:
        """Drop old / excess events and rebuild index if needed."""
        cutoff = time.time() - RETENTION_SECONDS
        before = len(self._events)
        self._events = [e for e in self._events if float(e.get("ts", 0)) >= cutoff]
        if len(self._events) > MAX_EVENTS:
            self._events = self._events[-MAX_EVENTS:]
        if len(self._events) != before:
            self._rebuild_index()
