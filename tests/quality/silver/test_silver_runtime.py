"""Silver: runtime reliability (empty safety, orphans, categories)."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.furbulous.empty_safety import (
    arm_empty,
    consume_empty_arm,
    disarm_empty,
    is_empty_armed,
)
from custom_components.furbulous.registry import (
    _is_orphan_screen_control,
    async_remove_orphan_entities,
)
from custom_components.furbulous.switch import (
    FurbulousChildLockSwitch,
    FurbulousDNDSwitch,
    FurbulousEmptyConfirmSwitch,
    FurbulousFullAutoModeSwitch,
)


def test_empty_safety_arm_consume_disarm():
    device_id = 99
    disarm_empty(device_id)
    assert not is_empty_armed(device_id)
    assert not consume_empty_arm(device_id)

    arm_empty(device_id)
    assert is_empty_armed(device_id)
    assert consume_empty_arm(device_id) is True
    # Consumed — second press fails
    assert not is_empty_armed(device_id)
    assert not consume_empty_arm(device_id)

    arm_empty(device_id)
    disarm_empty(device_id)
    assert not consume_empty_arm(device_id)


def test_orphan_screen_button_detection():
    class E:
        def __init__(self, domain, unique_id):
            self.domain = domain
            self.unique_id = unique_id

    assert _is_orphan_screen_control(E("button", "iot-x_screen_on"))
    assert _is_orphan_screen_control(E("button", "iot-x_screen_off"))
    assert _is_orphan_screen_control(E("switch", "furbulous_1_screen_off"))
    assert not _is_orphan_screen_control(E("switch", "iot-x_energy_saving_switch"))
    assert not _is_orphan_screen_control(E("button", "iot-x_dump"))


async def test_async_remove_orphan_entities_noop_without_registry(hass_if_available=None):
    """Function is importable; full HA registry test lives in init_ha when present."""
    assert callable(async_remove_orphan_entities)


def test_settings_switches_are_config_category():
    coord = MagicMock()
    coord.data = {"devices": [{"id": 1, "iotid": "i", "properties": {}}]}
    coord.last_update_success = True
    api = MagicMock()
    for cls in (
        FurbulousFullAutoModeSwitch,
        FurbulousDNDSwitch,
        FurbulousChildLockSwitch,
    ):
        sw = cls(coord, api, 1, "i")
        assert sw.entity_category == "config" or str(sw.entity_category) == "config"


def test_empty_confirm_is_controls_not_config():
    coord = MagicMock()
    coord.data = {"devices": [{"id": 1, "iotid": "i", "properties": {}}]}
    coord.last_update_success = True
    sw = FurbulousEmptyConfirmSwitch(coord, MagicMock(), 1, "i")
    assert sw.entity_category is None
