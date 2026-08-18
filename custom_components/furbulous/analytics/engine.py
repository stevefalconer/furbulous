"""Edge detection + command hooks + metric cache for Furbulous analytics.

Pi-friendly design:
- Presence path (~30s): edge detection only; full rollup only when events change;
  while full, update ``current_time_full_s`` cheaply without rescanning history.
- Full path (~5 min): recompute rollups (hours-since style gauges refresh here).
- Disk flush is debounced (default 60s) and skipped when not dirty.
- Entity listeners should fingerprint before ``async_write_ha_state``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from ..entity import extract_prop_value
from ..error_report import is_waste_full
from ..events import (
    EVENT_BAG_REPLACED,
    EVENT_LITTER_RESET,
    EVENT_PACK,
    EVENT_VISIT_ENDED,
    EVENT_WASTE_CLEARED,
    EVENT_WASTE_FULL,
    emit_event,
)
from ..weight import resolve_cat_weight_grams
from .metrics import UNKNOWN_LABEL, compute_device_metrics, compute_pet_metrics
from .pet_match import (
    is_plausible_cat_weight,
    learn_from_visit_events,
    resolve_visit_identity,
    stable_visit_weight_g,
    update_learned_weight,
)
from .store import EventStore

_LOGGER = logging.getLogger(__name__)

VISIT_DEBOUNCE_S = 20.0
FULL_CONFIRM_POLLS = 2
BAG_EMPTY_DEBOUNCE_S = 300.0  # 5 min
LITTER_RESET_DEBOUNCE_S = 600.0  # 10 min
HAND_MODE_EMPTY = 2
HAND_MODE_PACK = 3
FLUSH_DEBOUNCE_S = 60.0


def _is_full(props: dict[str, Any]) -> bool:
    return is_waste_full(props.get("errorReportEvent"))


def _is_occupied(props: dict[str, Any]) -> bool:
    from ..helpers import is_cat_present

    return is_cat_present(props)


def _normalize_pet(pet: dict[str, Any]) -> dict[str, Any]:
    """Map API fields (nickname, pet_id) onto id/name used by matching + HA pets."""
    out = dict(pet)
    if out.get("id") is None and out.get("pet_id") is not None:
        out["id"] = out["pet_id"]
    if not out.get("name"):
        out["name"] = out.get("nickname") or out.get("pet_name") or ""
    return out


def _pet_roster_signature(pets: list[dict[str, Any]]) -> tuple[tuple[Any, str], ...]:
    """Stable signature so unchanged pet lists do not force recompute."""
    items: list[tuple[Any, str]] = []
    for pet in pets:
        pid = pet.get("id") if pet.get("id") is not None else pet.get("pet_id")
        name = pet.get("name") or pet.get("nickname") or ""
        items.append((pid, str(name)))
    return tuple(sorted(items, key=lambda x: (str(x[0]), x[1])))


class AnalyticsEngine:
    """Process coordinator snapshots into events and cached metrics."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.store = EventStore(hass, entry_id)
        self._listeners: list[Callable[[], None]] = []
        self._device_state: dict[str, dict[str, Any]] = {}
        self.device_metrics: dict[str, dict[str, Any]] = {}
        self.pet_metrics: dict[str, dict[str, Any]] = {}
        self.pets: list[dict[str, Any]] = []
        self._pets_sig: tuple[tuple[Any, str], ...] = ()
        self._learned_weights: dict[str, float] = {}
        self._dirty = False
        self._need_immediate_flush = False
        self._last_save = 0.0
        self._flush_task: Any | None = None
        self._delayed_flush_task: Any | None = None

    async def async_setup(self) -> None:
        """Load persisted events and restore open chore cycles."""
        await self.store.async_load()
        self._learned_weights = learn_from_visit_events(self.store.events)
        self._restore_device_state_from_events()
        self.recompute_all()

    def _restore_device_state_from_events(self) -> None:
        """Restart-safe: reopen full episodes + last bag/litter markers from log.

        Cat-lover BA requirement: after HA reboot, “time full (current)” and
        bag/litter intervals must not reset to empty if events were stored.
        """
        for did in self.store.device_ids:
            st = self._device_state.setdefault(
                did,
                {
                    "occupied": False,
                    "occupy_since": None,
                    "is_full": False,
                    "full_true_polls": 0,
                    "full_episode_start": None,
                    "last_bag_ts": None,
                    "last_litter_reset_ts": None,
                    "name": None,
                    "iotid": None,
                    "last_pet_id": None,
                    "last_pet_name": UNKNOWN_LABEL,
                    "last_visitor_name": UNKNOWN_LABEL,
                    "last_visitor_id": None,
                    "visit_weight_g": None,
                    "last_visit_ts": None,
                    "last_visit_weight_g": None,
                },
            )
            events = self.store.events_for_device(did)
            last_bag = None
            last_litter = None
            last_full_on = None
            last_full_off = None
            last_visit_name = UNKNOWN_LABEL
            last_visit_id = None
            last_visit_ts = None
            last_visit_weight = None
            for ev in events:
                et = ev.get("event_type")
                ts = float(ev.get("ts", 0))
                if et == "bag_replaced":
                    last_bag = ts
                elif et == "litter_reset":
                    last_litter = ts
                elif et == "waste_full_on":
                    last_full_on = ts
                elif et == "waste_full_off":
                    last_full_off = ts
                elif et == "visit_ended":
                    payload = ev.get("payload") or {}
                    pname = payload.get("pet_name")
                    last_visit_name = pname if pname else UNKNOWN_LABEL
                    last_visit_id = payload.get("pet_id")
                    last_visit_ts = ts
                    if payload.get("weight_g") is not None:
                        try:
                            last_visit_weight = float(payload["weight_g"])
                        except (TypeError, ValueError):
                            pass
                iotid = ev.get("iotid")
                if iotid:
                    st["iotid"] = iotid
            if last_bag is not None:
                st["last_bag_ts"] = last_bag
            if last_litter is not None:
                st["last_litter_reset_ts"] = last_litter
            if last_visit_ts is not None:
                st["last_visit_ts"] = last_visit_ts
                st["last_visit_weight_g"] = last_visit_weight
                st["last_visitor_name"] = last_visit_name or UNKNOWN_LABEL
                st["last_visitor_id"] = last_visit_id
            # Open full episode if last transition was to full
            if last_full_on is not None and (
                last_full_off is None or last_full_on > last_full_off
            ):
                st["is_full"] = True
                st["full_episode_start"] = last_full_on
                st["full_true_polls"] = FULL_CONFIRM_POLLS

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a metrics-changed listener; returns unsubscribe."""
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
                _LOGGER.exception("Analytics listener failed")

    @property
    def is_dirty(self) -> bool:
        """True when events need to be persisted."""
        return self._dirty

    async def async_flush(self, *, force: bool = False) -> None:
        """Persist if dirty; debounce writes to spare SD card on Pi.

        If debounce blocks a save, a delayed retry is scheduled so dirty data
        is not stranded until the next event (or unload).
        """
        if not self._dirty:
            return
        now = time.time()
        if not force and (now - self._last_save) < FLUSH_DEBOUNCE_S:
            remaining = FLUSH_DEBOUNCE_S - (now - self._last_save)
            self._schedule_delayed_flush(remaining)
            return
        await self.store.async_save()
        self._dirty = False
        self._last_save = now

    def _schedule_delayed_flush(self, delay_s: float) -> None:
        """Ensure one delayed flush runs after the debounce window."""
        if self._delayed_flush_task is not None and not self._delayed_flush_task.done():
            return

        async def _later() -> None:
            try:
                await asyncio.sleep(max(0.1, delay_s))
                await self.async_flush(force=True)
            except asyncio.CancelledError:
                raise
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Delayed analytics flush failed", exc_info=True)

        self._delayed_flush_task = self.hass.async_create_task(_later())

    def schedule_flush(self) -> None:
        """Flush now for visit/bag/litter edges; debounce idle rollups."""
        if not self._dirty:
            return
        if self._flush_task is not None and not self._flush_task.done():
            return
        force = self._need_immediate_flush
        self._need_immediate_flush = False
        self._flush_task = self.hass.async_create_task(self.async_flush(force=force))

    def recompute_all(self) -> None:
        """Recompute metrics for all known devices + pets."""
        now = time.time()
        device_ids = set(self._device_state.keys()) | self.store.device_ids

        device_names: dict[str, str] = {}
        for did, st in self._device_state.items():
            if st.get("name"):
                device_names[did] = st["name"]

        for did in device_ids:
            if not did or did == "None":
                continue
            st = self._device_state.get(did, {})
            events = self.store.events_for_device(did)
            self.device_metrics[did] = compute_device_metrics(
                events,
                now=now,
                open_full_start=st.get("full_episode_start"),
                is_full=bool(st.get("is_full")),
            )

        all_visits = self.store.events_all(event_types={"visit_ended"})
        self.pet_metrics = {}
        for pet in self.pets:
            pid = pet.get("id")
            name = pet.get("name") or UNKNOWN_LABEL
            key = str(pid) if pid is not None else name
            self.pet_metrics[key] = compute_pet_metrics(
                all_visits,
                pid,
                name,
                device_names,
                now=now,
            )

    def _refresh_live_full_wait(self) -> bool:
        """Update only current_time_full_s for boxes that are full. O(devices)."""
        now = time.time()
        updated = False
        for did, st in self._device_state.items():
            if not st.get("is_full"):
                m = self.device_metrics.get(did)
                if m is not None and m.get("current_time_full_s"):
                    m["current_time_full_s"] = 0.0
                    updated = True
                continue
            start = st.get("full_episode_start")
            if start is None:
                continue
            metrics = self.device_metrics.get(did)
            if metrics is None:
                metrics = {}
                self.device_metrics[did] = metrics
            metrics["current_time_full_s"] = max(0.0, now - float(start))
            updated = True
        return updated

    def process_snapshot(
        self,
        devices: list[dict[str, Any]],
        *,
        pets: list[dict[str, Any]] | None = None,
        full_recompute: bool = False,
    ) -> bool:
        """Process a full or presence snapshot.

        Args:
            full_recompute: When True (5 min full poll), always refresh rollups
                including hours-since gauges. When False (30s presence), only
                recompute if edges fired; otherwise cheap live-full update.
        """
        # 0 = idle, 1 = new events (needs rollup + persist), 2 = soft UI-only change
        rank = 0
        if pets is not None:
            # Normalize API roster (nickname/pet_id) for matching + pet devices
            normalized = [_normalize_pet(p) for p in pets]
            sig = _pet_roster_signature(normalized)
            if sig != self._pets_sig:
                self.pets = normalized
                self._pets_sig = sig
                rank = 1

        # Presence owns occupy / full / workstatus-8 edges. The 5 min snapshot
        # can arrive stale and open a false visit after presence already
        # classified a clean. Pets + WC history stay on the full path.
        detect_edges = not full_recompute
        for device in devices:
            if device.get("id") is None:
                continue
            if detect_edges:
                rank = max(rank, self._process_device(device))
            # Hydrate Last cat from cloud visit history (full poll only)
            if full_recompute and device.get("wc_history") is not None:
                if self.ingest_wc_history(device):
                    rank = 1

        if rank == 1 or full_recompute:
            self.recompute_all()
            if rank == 1:
                self._dirty = True
                self._need_immediate_flush = True
            self._notify()
            return rank == 1

        # Soft UI change (e.g. pet name while occupied) or live full wait only
        live = self._refresh_live_full_wait()
        if live or rank == 2:
            self._notify()
        return False

    def _process_device(self, device: dict[str, Any]) -> int:
        """Return 0 idle, 1 event-level change, 2 soft (identity label only)."""
        did = str(device.get("id"))
        iotid = device.get("iotid")
        props = device.get("properties") or {}
        name = device.get("name")
        occupied = _is_occupied(props)
        full = _is_full(props)
        weight_now = resolve_cat_weight_grams(props)
        live_match = resolve_visit_identity(
            props, weight_now, self.pets, self._learned_weights
        )
        pet_id, pet_name = live_match.pet_id, live_match.display_name
        now = time.time()

        st = self._device_state.setdefault(
            did,
            {
                "occupied": False,
                "occupy_since": None,
                "is_full": False,
                "full_true_polls": 0,
                "full_episode_start": None,
                "last_bag_ts": None,
                "last_litter_reset_ts": None,
                "name": name,
                "iotid": iotid,
                "last_pet_id": None,
                "last_pet_name": UNKNOWN_LABEL,
                "last_visitor_name": UNKNOWN_LABEL,
                "last_visitor_id": None,
                "last_match_method": None,
                "last_match_confidence": None,
                "last_match_delta_g": None,
                "visit_weight_samples": [],
                "visit_weight_g": None,
                "last_visit_ts": None,
                "last_visit_weight_g": None,
            },
        )
        if name:
            st["name"] = name
        if iotid:
            st["iotid"] = iotid

        prev_work = st.get("last_workstatus")
        try:
            work_now = int(extract_prop_value(props.get("workstatus")))
        except (TypeError, ValueError):
            work_now = None
        st["last_workstatus"] = work_now
        if work_now == 8 and prev_work != 8:
            self.record_litter_reset(did, iotid, source="device")
            rank = 1

        # Collect weight samples while occupied; median at end resists noise
        if occupied and is_plausible_cat_weight(weight_now):
            samples = list(st.get("visit_weight_samples") or [])
            samples.append(float(weight_now))
            # Cap sample list (presence ~30s; long sits still bounded)
            st["visit_weight_samples"] = samples[-40:]
            st["visit_weight_g"] = stable_visit_weight_g(samples)

        identity_changed = (
            st.get("last_pet_id") != pet_id or st.get("last_pet_name") != pet_name
        )
        # Live occupying name only while occupied
        if occupied:
            st["last_pet_id"] = pet_id
            st["last_pet_name"] = pet_name

        rank = 0

        # --- occupancy / visits ---
        was_occ = bool(st.get("occupied"))
        if occupied and not was_occ:
            st["occupied"] = True
            st["occupy_since"] = now
            st["last_pet_id"] = pet_id
            st["last_pet_name"] = pet_name
            samples = (
                [float(weight_now)] if is_plausible_cat_weight(weight_now) else []
            )
            st["visit_weight_samples"] = samples
            st["visit_weight_g"] = stable_visit_weight_g(samples)
            self.store.append(
                "visit_started",
                device_id=did,
                iotid=iotid,
                source="presence",
                payload={
                    "pet_id": pet_id,
                    "pet_name": pet_name,
                    "weight_g": st.get("visit_weight_g"),
                    "identity_method": live_match.method,
                    "identity_confidence": live_match.confidence,
                },
                ts=now,
            )
            rank = 1
        elif not occupied and was_occ:
            start = st.get("occupy_since") or now
            duration = max(0.0, now - float(start))
            samples = list(st.get("visit_weight_samples") or [])
            if is_plausible_cat_weight(weight_now):
                samples.append(float(weight_now))
            end_weight = stable_visit_weight_g(samples)
            # Final identity: weight-first (app) using median visit weight
            end_match = resolve_visit_identity(
                props, end_weight, self.pets, self._learned_weights
            )
            end_pet_id = end_match.pet_id
            end_pet_name = end_match.display_name
            end_method = end_match.method
            end_conf = end_match.confidence
            end_delta = end_match.delta_g
            # Exit poll often drops petName; keep best identity seen while occupied
            if end_pet_name in (None, "", "-", UNKNOWN_LABEL):
                prior = st.get("last_pet_name")
                if prior and prior not in (None, "", "-", UNKNOWN_LABEL):
                    end_pet_name = prior
                    end_pet_id = st.get("last_pet_id") or end_pet_id
                    end_method = end_method if end_method != "none" else "visit_carry"
                    end_conf = end_conf if end_conf != "none" else "medium"
            st["occupied"] = False
            st["occupy_since"] = None
            st["visit_weight_samples"] = []
            st["visit_weight_g"] = None
            if duration >= VISIT_DEBOUNCE_S:
                visit_payload = {
                    "duration_s": duration,
                    "pet_id": end_pet_id,
                    "pet_name": end_pet_name,
                    "weight_g": end_weight,
                    "weight_match_delta_g": end_delta,
                    "identity_method": end_method,
                    "identity_confidence": end_conf,
                    "second_pet": end_match.second_pet_name,
                    "second_delta_g": end_match.second_delta_g,
                }
                self.store.append(
                    "visit_ended",
                    device_id=did,
                    iotid=iotid,
                    source="presence",
                    payload=visit_payload,
                    ts=now,
                )
                emit_event(
                    self.hass,
                    EVENT_VISIT_ENDED,
                    {
                        "device_id": did,
                        "iotid": iotid,
                        "config_entry_id": self.entry_id,
                        **visit_payload,
                    },
                )
                st["last_visit_ts"] = now
                st["last_visit_weight_g"] = end_weight
                st["last_visitor_id"] = end_pet_id
                st["last_visitor_name"] = end_pet_name
                st["last_match_method"] = end_method
                st["last_match_confidence"] = end_conf
                st["last_match_delta_g"] = end_delta
                if end_weight is not None and end_pet_name not in (
                    None,
                    UNKNOWN_LABEL,
                    "",
                    "-",
                ):
                    update_learned_weight(
                        self._learned_weights,
                        end_pet_id,
                        end_pet_name,
                        float(end_weight),
                    )
                rank = 1

        # --- waste full episodes ---
        if full:
            st["full_true_polls"] = int(st.get("full_true_polls", 0)) + 1
            if (
                not st.get("is_full")
                and st["full_true_polls"] >= FULL_CONFIRM_POLLS
            ):
                st["is_full"] = True
                st["full_episode_start"] = now
                self.store.append(
                    "waste_full_on",
                    device_id=did,
                    iotid=iotid,
                    source="presence",
                    payload={},
                    ts=now,
                )
                emit_event(
                    self.hass,
                    EVENT_WASTE_FULL,
                    {
                        "device_id": did,
                        "iotid": iotid,
                        "config_entry_id": self.entry_id,
                    },
                )
                rank = 1
        else:
            st["full_true_polls"] = 0
            if st.get("is_full"):
                start = st.get("full_episode_start") or now
                time_full = max(0.0, now - float(start))
                st["is_full"] = False
                st["full_episode_start"] = None
                self.store.append(
                    "waste_full_off",
                    device_id=did,
                    iotid=iotid,
                    source="presence",
                    payload={"time_full_s": time_full, "cleared_how": "error_cleared"},
                    ts=now,
                )
                emit_event(
                    self.hass,
                    EVENT_WASTE_CLEARED,
                    {
                        "device_id": did,
                        "iotid": iotid,
                        "config_entry_id": self.entry_id,
                        "time_full_s": time_full,
                        "cleared_how": "error_cleared",
                    },
                )
                # Bag-full clear on the device usually means the sealed bag was
                # removed and the drawer put back — restart Bag age.
                self._record_bag_replaced(
                    did, iotid, source="presence", now=now
                )
                rank = 1

        if rank == 0 and identity_changed and occupied:
            return 2
        return rank

    def _record_bag_replaced(
        self,
        device_id: str,
        iotid: str | None,
        *,
        source: str,
        now: float | None = None,
    ) -> bool:
        """Append bag_replaced + update last_bag_ts. Returns False if debounced."""
        did = str(device_id)
        now = time.time() if now is None else now
        st = self._device_state.setdefault(did, {})
        last_bag = st.get("last_bag_ts")
        if last_bag is not None and (now - float(last_bag)) < BAG_EMPTY_DEBOUNCE_S:
            _LOGGER.debug("Ignoring debounced bag_replaced device=%s", did)
            return False
        lifetime_s = None
        if last_bag is not None:
            lifetime_s = now - float(last_bag)
        self.store.append(
            "bag_replaced",
            device_id=did,
            iotid=iotid,
            source=source,
            payload={"lifetime_s": lifetime_s},
            ts=now,
        )
        emit_event(
            self.hass,
            EVENT_BAG_REPLACED,
            {
                "device_id": did,
                "iotid": iotid,
                "config_entry_id": self.entry_id,
                "lifetime_s": lifetime_s,
                "source": source,
            },
        )
        st["last_bag_ts"] = now
        return True

    def record_hand_mode(
        self,
        device_id: str | int,
        iotid: str | None,
        hand_mode: int,
        *,
        source: str = "ha_button",
    ) -> None:
        """Record Empty/Pack (and bag close on Empty)."""
        did = str(device_id)
        now = time.time()
        st = self._device_state.setdefault(did, {})
        if hand_mode == HAND_MODE_PACK:
            self.store.append(
                "pack",
                device_id=did,
                iotid=iotid,
                source=source,
                payload={},
                ts=now,
            )
            emit_event(
                self.hass,
                EVENT_PACK,
                {
                    "device_id": did,
                    "iotid": iotid,
                    "config_entry_id": self.entry_id,
                    "source": source,
                },
            )
        elif hand_mode == HAND_MODE_EMPTY:
            last_bag = st.get("last_bag_ts")
            if last_bag is not None and (now - float(last_bag)) < BAG_EMPTY_DEBOUNCE_S:
                _LOGGER.debug("Ignoring debounced empty device=%s", did)
            else:
                self.store.append(
                    "empty",
                    device_id=did,
                    iotid=iotid,
                    source=source,
                    payload={},
                    ts=now,
                )
                self._record_bag_replaced(did, iotid, source=source, now=now)
                if st.get("is_full"):
                    start = st.get("full_episode_start") or now
                    time_full = max(0.0, now - float(start))
                    self.store.append(
                        "waste_full_off",
                        device_id=did,
                        iotid=iotid,
                        source=source,
                        payload={
                            "time_full_s": time_full,
                            "cleared_how": "empty",
                        },
                        ts=now,
                    )
                    emit_event(
                        self.hass,
                        EVENT_WASTE_CLEARED,
                        {
                            "device_id": did,
                            "iotid": iotid,
                            "config_entry_id": self.entry_id,
                            "time_full_s": time_full,
                            "cleared_how": "empty",
                        },
                    )
                    st["is_full"] = False
                    st["full_episode_start"] = None
                    st["full_true_polls"] = 0
        else:
            return

        self._dirty = True
        self._need_immediate_flush = True
        self.recompute_all()
        self._notify()

    def record_litter_reset(
        self,
        device_id: str | int,
        iotid: str | None,
        *,
        source: str = "ha_button",
    ) -> None:
        """Record litter reset (helper button or future API)."""
        did = str(device_id)
        now = time.time()
        st = self._device_state.setdefault(did, {})
        last = st.get("last_litter_reset_ts")
        if last is not None and (now - float(last)) < LITTER_RESET_DEBOUNCE_S:
            _LOGGER.debug("Ignoring debounced litter reset device=%s", did)
            return
        interval_s = (now - float(last)) if last is not None else None
        self.store.append(
            "litter_reset",
            device_id=did,
            iotid=iotid,
            source=source,
            payload={"interval_s": interval_s},
            ts=now,
        )
        self._need_immediate_flush = True
        emit_event(
            self.hass,
            EVENT_LITTER_RESET,
            {
                "device_id": did,
                "iotid": iotid,
                "config_entry_id": self.entry_id,
                "interval_s": interval_s,
                "source": source,
            },
        )
        st["last_litter_reset_ts"] = now
        self._dirty = True
        self.recompute_all()
        self._notify()

    def ingest_wc_history(self, device: dict[str, Any]) -> bool:
        """Import /device/data/wc visits into analytics (weight + time, match cat).

        Cloud records have no pet name — closest roster weight (lb unit fixed).
        Incremental: only rows with start_time > wc_ingested_through.
        """
        did = str(device.get("id"))
        iotid = device.get("iotid")
        rows = device.get("wc_history") or []
        if not rows:
            return False
        st = self._device_state.setdefault(did, {})
        # Resume watermark from prior WC events so HA restart does not re-append
        through = float(st.get("wc_ingested_through") or 0)
        if through <= 0:
            for ev in self.store.events_for_device(did, event_types={"visit_ended"}):
                if (ev.get("source") or "") != "wc_history":
                    continue
                try:
                    through = max(through, float(ev.get("ts") or 0))
                except (TypeError, ValueError):
                    continue
            # Also treat presence visits as known times to avoid double-count
            for ev in self.store.events_for_device(did, event_types={"visit_ended"}):
                try:
                    through = max(through, float(ev.get("ts") or 0) - 1)
                except (TypeError, ValueError):
                    continue
        known_ts = {
            round(float(ev.get("ts") or 0), 0)
            for ev in self.store.events_for_device(did, event_types={"visit_ended"})
        }
        # Sort ascending so through advances correctly
        ordered = sorted(
            (r for r in rows if isinstance(r, dict) and r.get("start_time")),
            key=lambda r: float(r["start_time"]),
        )
        added = 0
        latest_row: dict[str, Any] | None = None
        for row in ordered:
            try:
                ts = float(row["start_time"])
            except (TypeError, ValueError):
                continue
            latest_row = row
            if ts <= through or round(ts, 0) in known_ts:
                # Still allow Last cat refresh from latest row without re-append
                continue
            weight_g = row.get("weight")
            try:
                weight_f = float(weight_g) if weight_g is not None else None
            except (TypeError, ValueError):
                weight_f = None
            duration_s = None
            if row.get("minute") is not None or row.get("second") is not None:
                try:
                    duration_s = int(row.get("minute") or 0) * 60 + int(
                        row.get("second") or 0
                    )
                except (TypeError, ValueError):
                    duration_s = None
            match = resolve_visit_identity(
                {}, weight_f, self.pets, self._learned_weights
            )
            self.store.append(
                "visit_ended",
                device_id=did,
                iotid=iotid,
                source="wc_history",
                payload={
                    "duration_s": duration_s,
                    "pet_id": match.pet_id,
                    "pet_name": match.display_name,
                    "weight_g": weight_f,
                    "weight_match_delta_g": match.delta_g,
                    "identity_method": match.method,
                    "identity_confidence": match.confidence,
                    "second_pet": match.second_pet_name,
                    "second_delta_g": match.second_delta_g,
                },
                ts=ts,
            )
            known_ts.add(round(ts, 0))
            st["last_visit_ts"] = ts
            st["last_visit_weight_g"] = weight_f
            st["last_visitor_id"] = match.pet_id
            st["last_visitor_name"] = match.display_name
            st["last_match_method"] = match.method
            st["last_match_confidence"] = match.confidence
            st["last_match_delta_g"] = match.delta_g
            if weight_f is not None and match.display_name not in (
                None,
                UNKNOWN_LABEL,
                "",
                "-",
            ):
                update_learned_weight(
                    self._learned_weights,
                    match.pet_id,
                    match.display_name,
                    float(weight_f),
                )
            through = ts
            added += 1
        # If no new rows but WC has data, still refresh Last cat from latest
        if added == 0 and latest_row is not None and st.get("last_visit_ts") is None:
            try:
                ts = float(latest_row["start_time"])
                weight_f = (
                    float(latest_row["weight"])
                    if latest_row.get("weight") is not None
                    else None
                )
            except (TypeError, ValueError):
                ts, weight_f = None, None
            if ts is not None:
                match = resolve_visit_identity(
                    {}, weight_f, self.pets, self._learned_weights
                )
                st["last_visit_ts"] = ts
                st["last_visit_weight_g"] = weight_f
                st["last_visitor_id"] = match.pet_id
                st["last_visitor_name"] = match.display_name
                st["last_match_method"] = match.method or "wc_history"
                st["last_match_confidence"] = match.confidence
                st["last_match_delta_g"] = match.delta_g
                self._notify()
                return False
        if added:
            st["wc_ingested_through"] = through
            self._dirty = True
            _LOGGER.debug(
                "Ingested %s WC visits for device %s (through=%s)",
                added,
                did,
                through,
            )
            return True
        return False

    def is_occupied(self, device_id: str | int) -> bool:
        """True while the presence edge says a cat is in the box."""
        return bool(self._device_state.get(str(device_id), {}).get("occupied"))

    def occupying_pet(self, device_id: str | int) -> str:
        """Live occupying pet: name while occupied, else blank ``-``.

        Never shows the previous visitor after they leave.
        """
        st = self._device_state.get(str(device_id), {})
        if not st.get("occupied"):
            return UNKNOWN_LABEL  # EMPTY "-"
        name = st.get("last_pet_name")
        if not name or name == UNKNOWN_LABEL:
            return UNKNOWN_LABEL
        return str(name)

    def last_visitor(self, device_id: str | int) -> str:
        """Last completed visit pet name (``-`` if none / unidentified)."""
        st = self._device_state.get(str(device_id), {})
        if st.get("last_visit_ts") is not None:
            name = st.get("last_visitor_name")
            if name and name != UNKNOWN_LABEL and str(name).strip():
                return str(name)
            return UNKNOWN_LABEL
        events = self.store.events_for_device(
            device_id, event_types={"visit_ended"}
        )
        if not events:
            return UNKNOWN_LABEL
        name = (events[-1].get("payload") or {}).get("pet_name")
        if not name or name == UNKNOWN_LABEL:
            return UNKNOWN_LABEL
        return str(name)

    def last_visit_ts(self, device_id: str | int) -> float | None:
        """Unix timestamp of last completed visit end (HA shows local time)."""
        st = self._device_state.get(str(device_id), {})
        if st.get("last_visit_ts") is not None:
            return float(st["last_visit_ts"])
        events = self.store.events_for_device(
            device_id, event_types={"visit_ended"}
        )
        if not events:
            return None
        return float(events[-1].get("ts", 0)) or None

    def last_visit_weight_g(self, device_id: str | int) -> float | None:
        """Weight in grams from last completed visit (display converts to lb/kg)."""
        st = self._device_state.get(str(device_id), {})
        if st.get("last_visit_weight_g") is not None:
            try:
                return float(st["last_visit_weight_g"])
            except (TypeError, ValueError):
                pass
        events = self.store.events_for_device(
            device_id, event_types={"visit_ended"}
        )
        if not events:
            return None
        raw = (events[-1].get("payload") or {}).get("weight_g")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def metrics_for_device(self, device_id: str | int) -> dict[str, Any]:
        """Cached metrics for a box."""
        return self.device_metrics.get(str(device_id), {})

    def diagnostics_summary(self) -> dict[str, Any]:
        """Redaction-safe analytics stats for diagnostics."""
        return {
            "event_count": self.store.event_count,
            "device_state_count": len(self._device_state),
            "pet_count": len(self.pets),
            "dirty": self._dirty,
            "listener_count": len(self._listeners),
        }
