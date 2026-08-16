"""Cat weight helpers — native unit is always grams for HA conversion.

API research: only known field is ``catWeight`` (grams). No separate kg/lb
property in the reverse-engineered client. HA converts g → lb/kg for display.
Do not convert for display in this integration.
"""
from __future__ import annotations

from typing import Any

_GRAM_KEYS = ("catWeight", "cat_weight", "weightG", "weight_g")
# If vendor ever ships these, normalize *to grams* so native UoM stays grams.
_KG_KEYS = ("catWeightKg", "cat_weight_kg", "weightKg", "weight_kg")
_LB_KEYS = ("catWeightLb", "catWeightLB", "cat_weight_lb", "weightLb", "weight_lb")

_LB_TO_G = 453.59237
_KG_TO_G = 1000.0


def _raw_value(prop: Any) -> Any:
    """Normalize {value, time} property payloads to a scalar."""
    if prop is None:
        return None
    if isinstance(prop, dict) and "value" in prop:
        return prop.get("value")
    return prop


def resolve_cat_weight_grams(properties: dict[str, Any] | None) -> float | None:
    """Return cat weight in **grams** (API-native / HA native unit).

    Preference: gram fields, then kg→g, then lb→g (normalization only).
    """
    if not properties:
        return None

    for key in _GRAM_KEYS:
        if key in properties:
            raw = _raw_value(properties[key])
            if raw is not None:
                return float(raw)

    for key in _KG_KEYS:
        if key in properties:
            raw = _raw_value(properties[key])
            if raw is not None:
                return float(raw) * _KG_TO_G

    for key in _LB_KEYS:
        if key in properties:
            raw = _raw_value(properties[key])
            if raw is not None:
                return float(raw) * _LB_TO_G

    return None


def source_weight_field(properties: dict[str, Any] | None) -> str | None:
    """Return which property key would be used for weight resolution."""
    if not properties:
        return None
    for key in (*_GRAM_KEYS, *_KG_KEYS, *_LB_KEYS):
        if key in properties and _raw_value(properties[key]) is not None:
            return key
    return None
