"""Cat weight helpers — API grams → HA display unit (lb or kg).

The cloud API exposes ``catWeight`` in grams. Home Assistant's unit-system
auto-conversion for weight is sticky/unreliable for already-registered
entities (unlike temperature). This module therefore:

1. Resolves API weight to grams.
2. Picks **lb** (US Customary) or **kg** (metric) from HA unit system.
3. Converts so ``native_value`` + ``native_unit_of_measurement`` match the UI.

Important HA fact: ``METRIC_SYSTEM.mass_unit`` is **grams** (``g``), not kg.
We still display **kg** for metric users (product requirement) and **lb** for
US Customary — never leave cat weight as raw grams in the UI.
"""
from __future__ import annotations

from typing import Any

# String values match homeassistant.const.UnitOfMass
UNIT_LB = "lb"
UNIT_OZ = "oz"
UNIT_KG = "kg"
UNIT_G = "g"

_GRAM_KEYS = ("catWeight", "cat_weight", "weightG", "weight_g")
_KG_KEYS = ("catWeightKg", "cat_weight_kg", "weightKg", "weight_kg")
_LB_KEYS = ("catWeightLb", "catWeightLB", "cat_weight_lb", "weightLb", "weight_lb")

_LB_TO_G = 453.59237
_KG_TO_G = 1000.0
_G_PER_LB = _LB_TO_G
_G_PER_KG = _KG_TO_G

_US_MASS_UNITS = frozenset(
    {UNIT_LB, UNIT_OZ, "lbs", "pound", "pounds", "ounce", "ounces"}
)
# Never use these as the sensor native unit for cat weight UI
_METRIC_MASS_HINTS = frozenset({UNIT_G, UNIT_KG, "gram", "grams", "kilogram", "kilograms"})


def _raw_value(prop: Any) -> Any:
    """Normalize {value, time} property payloads to a scalar."""
    if prop is None:
        return None
    if isinstance(prop, dict) and "value" in prop:
        return prop.get("value")
    return prop


def resolve_cat_weight_grams(properties: dict[str, Any] | None) -> float | None:
    """Return cat weight in **grams** (API storage unit)."""
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


def _mass_unit_str(mass_unit: Any) -> str:
    """Normalize UnitOfMass enum / string to lowercase token."""
    if mass_unit is None:
        return ""
    # StrEnum / enum → value; otherwise str
    value = getattr(mass_unit, "value", mass_unit)
    text = str(value).strip().lower()
    # "UnitOfMass.POUNDS" style from some mocks
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def preferred_display_mass_unit(hass: Any | None) -> str:
    """Return **lb** or **kg** for the weight sensor (never grams).

    Detection order:
    1. ``hass.config.units is US_CUSTOMARY_SYSTEM`` (real HA)
    2. ``units.mass_unit`` in {lb, oz} → lb
    3. Everything else (including metric mass_unit ``g``) → **kg**
    """
    if hass is None:
        return UNIT_KG

    try:
        units = hass.config.units
    except (AttributeError, TypeError):
        return UNIT_KG

    # Prefer identity check against HA unit system singletons
    try:
        from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

        if units is US_CUSTOMARY_SYSTEM:
            return UNIT_LB
    except Exception:  # pylint: disable=broad-except
        pass

    # Name fallback (some stubs / older paths)
    name = getattr(units, "name", None) or getattr(units, "_name", None)
    if name in ("us_customary", "imperial"):
        return UNIT_LB

    mass_str = _mass_unit_str(getattr(units, "mass_unit", None))
    if mass_str in _US_MASS_UNITS or mass_str in ("pounds", "ounces", "lb", "oz"):
        return UNIT_LB

    # Some HA builds expose unit_system as a mapping / as_dict
    try:
        as_dict = getattr(units, "as_dict", None)
        if callable(as_dict):
            mass_str = _mass_unit_str(as_dict().get("mass"))
            if mass_str in _US_MASS_UNITS or mass_str in ("lb", "oz", "pounds"):
                return UNIT_LB
    except Exception:  # pylint: disable=broad-except
        pass

    # Metric HA uses mass_unit=g — product still shows kg, not g
    return UNIT_KG


def convert_grams_to_unit(grams: float, unit: str) -> float:
    """Convert grams to ``lb`` or ``kg`` (``g`` passthrough only for tests)."""
    unit_norm = _mass_unit_str(unit) or UNIT_KG
    if unit_norm in _US_MASS_UNITS or unit_norm == UNIT_LB:
        return grams / _G_PER_LB
    if unit_norm == UNIT_G:
        return grams
    return grams / _G_PER_KG


def resolve_cat_weight_for_display(
    properties: dict[str, Any] | None,
    hass: Any | None,
) -> tuple[float | None, str]:
    """Return ``(value, unit)`` for the weight sensor (unit is always lb or kg)."""
    grams = resolve_cat_weight_grams(properties)
    unit = preferred_display_mass_unit(hass)
    # Guard: never expose grams as the display unit
    if unit == UNIT_G:
        unit = UNIT_KG
    if grams is None:
        return None, unit
    return convert_grams_to_unit(grams, unit), unit


def assert_display_not_grams(unit: str, value: float | None) -> None:
    """Test helper: display unit must be lb/kg; value scale must match."""
    assert unit in (UNIT_LB, UNIT_KG), f"display unit must be lb or kg, got {unit!r}"
    if value is None:
        return
    # Typical cat 2–12 kg ≈ 4–26 lb; raw grams would be thousands
    if unit == UNIT_KG:
        assert value < 100, f"kg value looks like grams: {value}"
    if unit == UNIT_LB:
        assert value < 200, f"lb value looks like grams: {value}"
