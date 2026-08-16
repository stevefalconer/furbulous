"""Pure rollup math from analytics events (no I/O)."""
from __future__ import annotations

import time
from typing import Any

# Text/enum empty display for cat lovers (numeric sensors use None, not "-")
EMPTY_LABEL = "-"
NONE_LABEL = EMPTY_LABEL  # averages / missing text metrics
NEVER_LABEL = EMPTY_LABEL
UNKNOWN_LABEL = EMPTY_LABEL  # unidentified visitor (not the word "Unknown")
NOT_ENOUGH_DATA = EMPTY_LABEL

WINDOW_7D = 7 * 24 * 3600
WINDOW_30D = 30 * 24 * 3600
MIN_FAVORITE_VISITS = 3


def _now() -> float:
    return time.time()


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _gaps(timestamps: list[float]) -> list[float]:
    if len(timestamps) < 2:
        return []
    ordered = sorted(timestamps)
    return [ordered[i] - ordered[i - 1] for i in range(1, len(ordered))]


def _completed_lifetimes(
    replace_events: list[dict[str, Any]],
    *,
    end_since: float | None = None,
) -> list[float]:
    """Bag lifetimes from consecutive bag_replaced events (need ≥2)."""
    ordered = sorted(replace_events, key=lambda e: float(e.get("ts", 0)))
    lifetimes: list[float] = []
    for i in range(1, len(ordered)):
        end_ts = float(ordered[i]["ts"])
        if end_since is not None and end_ts < end_since:
            continue
        start_ts = float(ordered[i - 1]["ts"])
        # Prefer payload lifetime when present
        payload = ordered[i].get("payload") or {}
        if payload.get("lifetime_s") is not None:
            lifetimes.append(float(payload["lifetime_s"]))
        else:
            lifetimes.append(end_ts - start_ts)
    return lifetimes


def compute_device_metrics(
    events: list[dict[str, Any]],
    *,
    now: float | None = None,
    open_full_start: float | None = None,
    is_full: bool = False,
) -> dict[str, Any]:
    """Compute per-box chore + visit rollups from events."""
    now = now if now is not None else _now()
    since_7d = now - WINDOW_7D
    since_30d = now - WINDOW_30D

    visits = [e for e in events if e.get("event_type") == "visit_ended"]
    packs = [e for e in events if e.get("event_type") == "pack"]
    empties = [e for e in events if e.get("event_type") == "empty"]
    bags = [e for e in events if e.get("event_type") == "bag_replaced"]
    resets = [e for e in events if e.get("event_type") == "litter_reset"]
    full_offs = [e for e in events if e.get("event_type") == "waste_full_off"]

    visits_today_local = 0  # filled by caller using HA local day if desired
    visits_7d = sum(1 for e in visits if float(e["ts"]) >= since_7d)
    visits_30d = sum(1 for e in visits if float(e["ts"]) >= since_30d)

    durations_30d = [
        float((e.get("payload") or {}).get("duration_s", 0))
        for e in visits
        if float(e["ts"]) >= since_30d
        and (e.get("payload") or {}).get("duration_s") is not None
    ]
    avg_duration_30d = _mean(durations_30d)

    pack_ts = [float(e["ts"]) for e in packs]
    last_pack = max(pack_ts) if pack_ts else None
    packs_30d = sum(1 for t in pack_ts if t >= since_30d)
    pack_gaps_30d = [
        g
        for g in _gaps([t for t in pack_ts if t >= since_30d - WINDOW_30D])
        if True
    ]
    # Gaps whose later pack is in 30d window
    pack_ordered = sorted(pack_ts)
    pack_gap_list: list[float] = []
    for i in range(1, len(pack_ordered)):
        if pack_ordered[i] >= since_30d:
            pack_gap_list.append(pack_ordered[i] - pack_ordered[i - 1])

    last_bag = max((float(e["ts"]) for e in bags), default=None)
    bag_lifetimes_all = _completed_lifetimes(bags)
    bag_lifetimes_30d = _completed_lifetimes(bags, end_since=since_30d)
    last_lifetime = bag_lifetimes_all[-1] if bag_lifetimes_all else None
    bags_30d = sum(1 for e in bags if float(e["ts"]) >= since_30d)

    # Visits during last completed bag (between last two replaces)
    visits_last_bag = None
    ordered_bags = sorted(bags, key=lambda e: float(e["ts"]))
    if len(ordered_bags) >= 2:
        a, b = float(ordered_bags[-2]["ts"]), float(ordered_bags[-1]["ts"])
        visits_last_bag = sum(
            1 for e in visits if a <= float(e["ts"]) < b
        )
    elif len(ordered_bags) == 1 and last_bag is not None:
        visits_last_bag = sum(1 for e in visits if float(e["ts"]) >= last_bag)

    reset_ts = [float(e["ts"]) for e in resets]
    last_reset = max(reset_ts) if reset_ts else None
    resets_30d = sum(1 for t in reset_ts if t >= since_30d)
    reset_gaps: list[float] = []
    ordered_resets = sorted(reset_ts)
    for i in range(1, len(ordered_resets)):
        if ordered_resets[i] >= since_30d:
            reset_gaps.append(ordered_resets[i] - ordered_resets[i - 1])
    last_reset_interval = None
    if len(ordered_resets) >= 2:
        last_reset_interval = ordered_resets[-1] - ordered_resets[-2]

    clear_durations = [
        float((e.get("payload") or {}).get("time_full_s"))
        for e in full_offs
        if (e.get("payload") or {}).get("time_full_s") is not None
    ]
    clear_30d = [
        float((e.get("payload") or {}).get("time_full_s"))
        for e in full_offs
        if float(e["ts"]) >= since_30d
        and (e.get("payload") or {}).get("time_full_s") is not None
    ]
    last_clear = clear_durations[-1] if clear_durations else None
    episodes_30d = len(clear_30d)

    current_waiting = None
    if is_full and open_full_start is not None:
        current_waiting = max(0.0, now - open_full_start)

    visits_since_pack = None
    if last_pack is not None:
        visits_since_pack = sum(1 for e in visits if float(e["ts"]) > last_pack)

    return {
        "visits_7d": visits_7d,
        "visits_30d": visits_30d,
        "avg_duration_s_30d": avg_duration_30d,
        "avg_duration_sample_count": len(durations_30d),
        "last_pack_ts": last_pack,
        "hours_since_pack": (now - last_pack) / 3600 if last_pack else None,
        "packs_30d": packs_30d,
        "avg_hours_between_packs_30d": (
            _mean(pack_gap_list) / 3600 if pack_gap_list else None
        ),
        "pack_gap_sample_count": len(pack_gap_list),
        "visits_since_last_pack": visits_since_pack,
        "last_bag_replaced_ts": last_bag,
        "hours_since_bag_replaced": (
            (now - last_bag) / 3600 if last_bag else None
        ),
        "last_bag_lifetime_s": last_lifetime,
        "avg_bag_lifetime_s_30d": _mean(bag_lifetimes_30d),
        "bag_lifetime_sample_count": len(bag_lifetimes_30d),
        "bags_replaced_30d": bags_30d,
        "visits_during_last_bag": visits_last_bag,
        "last_litter_reset_ts": last_reset,
        "hours_since_litter_reset": (
            (now - last_reset) / 3600 if last_reset else None
        ),
        "last_litter_interval_s": last_reset_interval,
        "avg_litter_interval_s_30d": _mean(reset_gaps),
        "litter_interval_sample_count": len(reset_gaps),
        "litter_resets_30d": resets_30d,
        "last_time_to_clear_s": last_clear,
        "avg_time_to_clear_s_30d": _mean(clear_30d),
        "max_time_to_clear_s_30d": max(clear_30d) if clear_30d else None,
        "time_to_clear_sample_count": len(clear_30d),
        "full_episodes_30d": episodes_30d,
        "current_time_full_s": current_waiting if is_full else 0.0,
        "empties_30d": sum(1 for e in empties if float(e["ts"]) >= since_30d),
        "visits_today_hint": visits_today_local,
    }


def compute_pet_metrics(
    events: list[dict[str, Any]],
    pet_id: str | int | None,
    pet_name: str,
    device_names: dict[str, str],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Per-pet visit rollups across all boxes."""
    now = now if now is not None else _now()
    since_7d = now - WINDOW_7D
    since_30d = now - WINDOW_30D
    pid = str(pet_id) if pet_id is not None else None
    name_lower = (pet_name or "").strip().lower()

    def _match(ev: dict[str, Any]) -> bool:
        payload = ev.get("payload") or {}
        if pid and str(payload.get("pet_id")) == pid:
            return True
        pname = (payload.get("pet_name") or "").strip().lower()
        if name_lower and pname == name_lower and pname != "unknown":
            return True
        return False

    visits = [
        e
        for e in events
        if e.get("event_type") == "visit_ended" and _match(e)
    ]
    visits_7d = sum(1 for e in visits if float(e["ts"]) >= since_7d)
    visits_30d = sum(1 for e in visits if float(e["ts"]) >= since_30d)
    durations = [
        float((e.get("payload") or {}).get("duration_s"))
        for e in visits
        if float(e["ts"]) >= since_30d
        and (e.get("payload") or {}).get("duration_s") is not None
    ]
    last_ts = max((float(e["ts"]) for e in visits), default=None)

    # Favorite box in 30d
    counts: dict[str, int] = {}
    last_by_box: dict[str, float] = {}
    for e in visits:
        if float(e["ts"]) < since_30d:
            continue
        did = str(e.get("device_id") or "")
        counts[did] = counts.get(did, 0) + 1
        last_by_box[did] = max(last_by_box.get(did, 0), float(e["ts"]))

    favorite = NOT_ENOUGH_DATA
    if sum(counts.values()) >= MIN_FAVORITE_VISITS and counts:
        # max count, tie-break most recent
        best = sorted(
            counts.keys(),
            key=lambda d: (counts[d], last_by_box.get(d, 0)),
            reverse=True,
        )[0]
        favorite = device_names.get(best) or best or UNKNOWN_LABEL

    return {
        "pet_id": pid,
        "pet_name": pet_name or UNKNOWN_LABEL,
        "visits_7d": visits_7d,
        "visits_30d": visits_30d,
        "avg_duration_s_30d": _mean(durations),
        "last_seen_ts": last_ts,
        "favorite_box": favorite,
    }
