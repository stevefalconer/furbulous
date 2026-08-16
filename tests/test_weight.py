"""Thorough tests for cat weight: grams API → lb/kg UI (never grams)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.furbulous.weight import (
    UNIT_G,
    UNIT_KG,
    UNIT_LB,
    assert_display_not_grams,
    convert_grams_to_unit,
    preferred_display_mass_unit,
    resolve_cat_weight_for_display,
    resolve_cat_weight_grams,
    source_weight_field,
)

# Realistic cat: 4.5 kg = 4500 g ≈ 9.92 lb
CAT_G = 4500.0
CAT_KG = 4.5
CAT_LB = 4500.0 / 453.59237


def test_resolve_cat_weight_grams_default():
    props = {"catWeight": 4500}
    assert resolve_cat_weight_grams(props) == 4500.0
    assert source_weight_field(props) == "catWeight"


def test_resolve_nested_value_dict():
    props = {"catWeight": {"value": 3200, "time": 1}}
    assert resolve_cat_weight_grams(props) == 3200.0


def test_resolve_prefers_grams_over_kg():
    props = {"catWeight": 4500, "catWeightKg": 9.9}
    assert resolve_cat_weight_grams(props) == 4500.0


def test_resolve_kg_normalized_to_grams():
    props = {"catWeightKg": 4.5}
    assert resolve_cat_weight_grams(props) == pytest.approx(4500.0)


def test_resolve_lb_normalized_to_grams():
    props = {"catWeightLb": 10.0}
    assert resolve_cat_weight_grams(props) == pytest.approx(4535.9237)


def test_resolve_missing_returns_none():
    assert resolve_cat_weight_grams({}) is None
    assert resolve_cat_weight_grams(None) is None


def test_convert_grams_to_lb_and_kg_exact():
    assert convert_grams_to_unit(CAT_G, "kg") == pytest.approx(CAT_KG)
    assert convert_grams_to_unit(CAT_G, "lb") == pytest.approx(CAT_LB)
    assert convert_grams_to_unit(CAT_G, UNIT_KG) == pytest.approx(4.5)
    # Must NOT leave display as thousands of grams when converting to lb/kg
    assert convert_grams_to_unit(CAT_G, "lb") < 30
    assert convert_grams_to_unit(CAT_G, "kg") < 20


def test_preferred_display_us_lb_string():
    hass = MagicMock()
    hass.config.units.mass_unit = "lb"
    assert preferred_display_mass_unit(hass) == UNIT_LB


def test_preferred_display_us_oz_maps_to_lb():
    hass = MagicMock()
    hass.config.units.mass_unit = "oz"
    assert preferred_display_mass_unit(hass) == UNIT_LB


def test_preferred_display_metric_g_maps_to_kg_not_grams():
    """Real HA metric system uses mass_unit=g — we must show kg, not g."""
    hass = MagicMock()
    hass.config.units.mass_unit = "g"
    hass.config.units.name = "metric"
    unit = preferred_display_mass_unit(hass)
    assert unit == UNIT_KG
    assert unit != UNIT_G


def test_preferred_display_metric_kg():
    hass = MagicMock()
    hass.config.units.mass_unit = "kg"
    assert preferred_display_mass_unit(hass) == UNIT_KG


def test_preferred_display_none_hass_defaults_kg():
    assert preferred_display_mass_unit(None) == UNIT_KG


def test_resolve_for_display_us_never_grams():
    hass = MagicMock()
    hass.config.units.mass_unit = "lb"
    value, unit = resolve_cat_weight_for_display({"catWeight": CAT_G}, hass)
    assert unit == UNIT_LB
    assert value == pytest.approx(CAT_LB)
    assert_display_not_grams(unit, value)
    # Explicitly not raw grams
    assert value != CAT_G
    assert unit != UNIT_G


def test_resolve_for_display_metric_never_grams():
    hass = MagicMock()
    # Simulate real HA metric: mass_unit is grams
    hass.config.units.mass_unit = "g"
    value, unit = resolve_cat_weight_for_display({"catWeight": CAT_G}, hass)
    assert unit == UNIT_KG
    assert value == pytest.approx(CAT_KG)
    assert_display_not_grams(unit, value)
    assert value != CAT_G


def test_sensor_us_and_metric_via_entity():
    """Weight entity native_value/unit follow unit system (not grams)."""
    from custom_components.furbulous.sensor import FurbulousCatWeightSensor

    coord = MagicMock()
    coord.data = {
        "devices": [
            {
                "id": 7,
                "iotid": "iot-7",
                "name": "Box",
                "properties": {"catWeight": CAT_G},
            }
        ]
    }
    coord.last_update_success = True
    sensor = FurbulousCatWeightSensor(coord, 7)

    sensor.hass = MagicMock()
    sensor.hass.config.units.mass_unit = "lb"
    assert sensor.native_unit_of_measurement == UNIT_LB
    assert sensor.native_value == pytest.approx(CAT_LB)
    assert_display_not_grams(
        sensor.native_unit_of_measurement, sensor.native_value
    )

    sensor.hass.config.units.mass_unit = "g"  # HA metric
    assert sensor.native_unit_of_measurement == UNIT_KG
    assert sensor.native_value == pytest.approx(CAT_KG)
    assert_display_not_grams(
        sensor.native_unit_of_measurement, sensor.native_value
    )


def test_zero_and_small_weights():
    hass = MagicMock()
    hass.config.units.mass_unit = "lb"
    value, unit = resolve_cat_weight_for_display({"catWeight": 0}, hass)
    assert unit == UNIT_LB
    assert value == pytest.approx(0.0)


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("homeassistant.util.unit_system") is None,
    reason="real HA unit systems not installed",
)
def test_preferred_display_real_ha_unit_systems():
    """Against real Home Assistant METRIC_SYSTEM / US_CUSTOMARY_SYSTEM."""
    from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

    hass_us = MagicMock()
    hass_us.config.units = US_CUSTOMARY_SYSTEM
    assert preferred_display_mass_unit(hass_us) == UNIT_LB
    assert US_CUSTOMARY_SYSTEM.mass_unit == "lb" or str(
        US_CUSTOMARY_SYSTEM.mass_unit
    ) in ("lb", "UnitOfMass.POUNDS")

    hass_m = MagicMock()
    hass_m.config.units = METRIC_SYSTEM
    # Real HA metric mass is grams — we still return kg for UI
    assert str(METRIC_SYSTEM.mass_unit) in ("g", "UnitOfMass.GRAMS") or (
        getattr(METRIC_SYSTEM.mass_unit, "value", None) == "g"
    )
    assert preferred_display_mass_unit(hass_m) == UNIT_KG

    value_us, unit_us = resolve_cat_weight_for_display(
        {"catWeight": CAT_G}, hass_us
    )
    value_m, unit_m = resolve_cat_weight_for_display(
        {"catWeight": CAT_G}, hass_m
    )
    assert unit_us == UNIT_LB and value_us == pytest.approx(CAT_LB)
    assert unit_m == UNIT_KG and value_m == pytest.approx(CAT_KG)
    assert_display_not_grams(unit_us, value_us)
    assert_display_not_grams(unit_m, value_m)
