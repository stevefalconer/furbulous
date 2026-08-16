"""Smoke tests for entity base contracts (unique_id / has_entity_name)."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.furbulous.binary_sensor import FurbulousCatInBoxSensor
from custom_components.furbulous.sensor import FurbulousCatWeightSensor
from custom_components.furbulous.switch import FurbulousFullAutoModeSwitch


def _coord():
    c = MagicMock()
    c.data = {
        "devices": [
            {
                "id": 7,
                "iotid": "iot-7",
                "name": "Test Box",
                "properties": {"catWeight": 4000, "workstatus": 0},
            }
        ]
    }
    c.last_update_success = True
    return c


def test_weight_sensor_unique_id_and_naming():
    """Weight sensor uses stable unique_id, translation_key, has_entity_name."""
    sensor = FurbulousCatWeightSensor(_coord(), 7)
    assert sensor.has_entity_name is True
    assert sensor.translation_key == "cat_weight"
    assert sensor.unique_id == "furbulous_7_catWeight"
    assert sensor.native_value == 4000.0


def test_weight_suggested_unit_follows_mass_unit():
    """US mass unit (lb) is suggested; metric grams leaves suggestion unset."""
    from homeassistant.const import UnitOfMass

    sensor = FurbulousCatWeightSensor(_coord(), 7)
    sensor.hass = MagicMock()
    sensor.hass.config.units.mass_unit = UnitOfMass.POUNDS
    assert sensor.suggested_unit_of_measurement == UnitOfMass.POUNDS

    sensor.hass.config.units.mass_unit = UnitOfMass.GRAMS
    assert sensor.suggested_unit_of_measurement is None


def test_presence_sensor_unique_id():
    """Occupancy entity unique_id is stable."""
    sensor = FurbulousCatInBoxSensor(_coord(), 7)
    assert sensor.has_entity_name is True
    assert sensor.translation_key == "cat_in_litter_box"
    assert sensor.unique_id == "furbulous_7_cat_in_box"


def test_switch_unique_id():
    """Switch unique_id includes iotid for stability."""
    sw = FurbulousFullAutoModeSwitch(_coord(), MagicMock(), 7, "iot-7")
    assert sw.has_entity_name is True
    assert sw.unique_id == "iot-7_full_auto_mode_switch"
