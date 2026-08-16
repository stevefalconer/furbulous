"""Multi-cat identity: native API fields + closest weight (app-style).

Furbulous multi-cat boxes (and similar smart boxes) typically identify cats by
comparing the visit's measured weight to each pet's profile weight and choosing
the nearest match. The vendor app also stores roster weights on the account.

This module implements that approach for multi-box households (e.g. 5 cats /
3–4 boxes):

1. Prefer native property fields (petId / petName) when present and non-empty.
2. Else match measured visit weight to the closest roster/learned weight.
3. Report confidence so the UI can be honest when two cats are similar.

Weights are always compared in grams.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Typical adult domestic cats ~2–10 kg; reject noise outside this for matching
MIN_CAT_G = 1500.0
MAX_CAT_G = 12000.0

# If best and 2nd-best deltas are this close, mark ambiguous (still assign closest)
AMBIGUOUS_GAP_G = 200.0


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result of identifying who used a litter box."""

    pet_id: Any | None
    pet_name: str
    method: str  # api_id | api_name | weight_closest | single_pet | none
    confidence: str  # high | medium | low | none
    weight_g: float | None
    delta_g: float | None
    second_delta_g: float | None = None
    second_pet_name: str | None = None

    @property
    def display_name(self) -> str:
        """Name for HA UI; ``-`` when unidentified."""
        if self.pet_name and self.pet_name not in ("-", "Unknown", "unknown", ""):
            return self.pet_name
        return "-"


def extract_pet_weight_grams(pet: dict[str, Any]) -> float | None:
    """Parse a pet roster dict into grams."""
    for key in (
        "weight",
        "weightG",
        "weight_g",
        "catWeight",
        "petWeight",
        "weightKg",
        "weight_kg",
        "weightLB",
        "weightLb",
        "weight_lb",
        "mass",
        "weightValue",
    ):
        if key not in pet:
            continue
        raw = pet.get(key)
        if isinstance(raw, dict):
            raw = raw.get("value", raw.get("weight", raw.get("g")))
        if raw is None or raw == "":
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        key_l = key.lower()
        if "lb" in key_l:
            return val * 453.59237
        if "kg" in key_l:
            return val * 1000.0
        # Bare weight: app often stores kg (3.5–8); large = already grams
        if key_l in ("weight", "mass", "petweight", "catweight", "weightvalue"):
            if val < 80:
                return val * 1000.0
            return val
        return val
    return None


def is_plausible_cat_weight(weight_g: float | None) -> bool:
    """True if weight looks like a cat (not litter bag / noise)."""
    if weight_g is None:
        return False
    return MIN_CAT_G <= float(weight_g) <= MAX_CAT_G


def reference_weight_g(
    pet: dict[str, Any],
    learned: dict[str, float] | None = None,
) -> float | None:
    """Roster field first, then learned EMA for that pet."""
    w = extract_pet_weight_grams(pet)
    if w is not None and is_plausible_cat_weight(w):
        return w
    if not learned:
        return None
    pid = pet.get("id")
    if pid is not None and str(pid) in learned:
        return learned[str(pid)]
    name = (pet.get("name") or "").strip().lower()
    if name and name in learned:
        return learned[name]
    return None


def stable_visit_weight_g(samples: list[float]) -> float | None:
    """Median of plausible samples during a visit (resists litter/sensor noise)."""
    good = sorted(s for s in samples if is_plausible_cat_weight(s))
    if not good:
        return None
    mid = len(good) // 2
    if len(good) % 2:
        return good[mid]
    return (good[mid - 1] + good[mid]) / 2.0


def match_closest_pet(
    weight_g: float | None,
    pets: list[dict[str, Any]],
    learned: dict[str, float] | None = None,
) -> MatchResult:
    """Pick the roster cat with the smallest |weight − profile| (always closest)."""
    empty = MatchResult(
        None, "-", "none", "none", weight_g, None, None, None
    )
    if not is_plausible_cat_weight(weight_g) or not pets:
        return empty

    scored: list[tuple[float, dict[str, Any]]] = []
    for pet in pets:
        ref = reference_weight_g(pet, learned)
        if ref is None:
            continue
        scored.append((abs(ref - float(weight_g)), pet))

    if not scored:
        # No profiles: single cat → assign; multi → cannot weight-match yet
        if len(pets) == 1 and pets[0].get("name"):
            return MatchResult(
                pets[0].get("id"),
                str(pets[0]["name"]),
                "single_pet",
                "medium",
                weight_g,
                None,
            )
        return empty

    scored.sort(key=lambda x: x[0])
    best_delta, best_pet = scored[0]
    second_delta = scored[1][0] if len(scored) > 1 else None
    second_name = (
        str(scored[1][1].get("name") or "") if len(scored) > 1 else None
    )

    # Confidence: tight match + clear gap to next cat
    if second_delta is None:
        confidence = "high" if best_delta <= 300 else "medium"
    else:
        gap = second_delta - best_delta
        if best_delta <= 250 and gap >= AMBIGUOUS_GAP_G:
            confidence = "high"
        elif best_delta <= 500 and gap >= 100:
            confidence = "medium"
        else:
            confidence = "low"  # still assign closest — like the app

    name = best_pet.get("name")
    return MatchResult(
        best_pet.get("id"),
        str(name) if name else "-",
        "weight_closest",
        confidence,
        weight_g,
        best_delta,
        second_delta,
        second_name or None,
    )


def identity_from_api_props(props: dict[str, Any]) -> tuple[Any | None, str | None]:
    """Native property identity if the device reports a current pet."""
    from ..entity import extract_prop_value

    id_keys = ("petId", "pet_id", "currentPetId", "catId", "cat_id", "petID")
    name_keys = (
        "petName",
        "pet_name",
        "currentPetName",
        "catName",
        "cat_name",
        "occupyingPet",
        "currentPet",
        "pet",
    )
    pet_id = None
    for key in id_keys:
        if key not in props:
            continue
        val = extract_prop_value(props[key])
        if val not in (None, "", 0, "0"):
            pet_id = val
            break
    pet_name = None
    for key in name_keys:
        if key not in props:
            continue
        val = extract_prop_value(props[key])
        if val in (None, "") or isinstance(val, (int, float, bool)):
            continue
        text = str(val).strip()
        if text and text.lower() not in ("unknown", "null", "none", "-", "0"):
            pet_name = text
            break
    return pet_id, pet_name


def resolve_visit_identity(
    props: dict[str, Any],
    weight_g: float | None,
    pets: list[dict[str, Any]],
    learned: dict[str, float] | None = None,
    *,
    prefer_weight: bool = True,
) -> MatchResult:
    """Full identity resolution for a visit (native API + closest weight).

    When ``prefer_weight`` is True (default, multi-cat): weight match wins when
    a plausible weight and at least one profile exist — matching the app.
    Native API name/id is used when weight matching is unavailable, or to
    resolve the display name after an id match.
    """
    api_id, api_name = identity_from_api_props(props)

    # Weight-first (app-like multi-cat)
    if prefer_weight and is_plausible_cat_weight(weight_g) and pets:
        wm = match_closest_pet(weight_g, pets, learned)
        if wm.pet_name and wm.pet_name != "-":
            # If API also gave an id, prefer weight result (app does weight)
            return wm

    # Native id → roster name
    if api_id is not None and pets:
        for pet in pets:
            if str(pet.get("id")) == str(api_id):
                name = pet.get("name") or api_name
                if name:
                    return MatchResult(
                        pet.get("id"),
                        str(name),
                        "api_id",
                        "high",
                        weight_g,
                        None,
                    )

    if api_name:
        return MatchResult(api_id, api_name, "api_name", "high", weight_g, None)

    # Single pet household without usable weights
    if len(pets) == 1 and pets[0].get("name"):
        return MatchResult(
            pets[0].get("id"),
            str(pets[0]["name"]),
            "single_pet",
            "medium",
            weight_g,
            None,
        )

    # Last resort weight match (may still work with learned only)
    if is_plausible_cat_weight(weight_g) and pets:
        return match_closest_pet(weight_g, pets, learned)

    return MatchResult(None, "-", "none", "none", weight_g, None)


def update_learned_weight(
    learned: dict[str, float],
    pet_id: Any | None,
    pet_name: str | None,
    weight_g: float,
    *,
    alpha: float = 0.35,
) -> None:
    """EMA of visit weights per pet — builds profiles when roster lacks weight."""
    if not is_plausible_cat_weight(weight_g):
        return
    keys: list[str] = []
    if pet_id is not None:
        keys.append(str(pet_id))
    if pet_name:
        n = pet_name.strip().lower()
        if n and n not in ("-", "unknown", "none"):
            keys.append(n)
    for key in keys:
        prev = learned.get(key)
        if prev is None:
            learned[key] = float(weight_g)
        else:
            learned[key] = (1.0 - alpha) * prev + alpha * float(weight_g)


def learn_from_visit_events(events: list[dict[str, Any]]) -> dict[str, float]:
    """Bootstrap learned weights from history (all boxes)."""
    learned: dict[str, float] = {}
    for ev in events:
        if ev.get("event_type") != "visit_ended":
            continue
        payload = ev.get("payload") or {}
        try:
            w = float(payload["weight_g"])
        except (KeyError, TypeError, ValueError):
            continue
        update_learned_weight(
            learned,
            payload.get("pet_id"),
            payload.get("pet_name"),
            w,
            alpha=0.45,
        )
    return learned
