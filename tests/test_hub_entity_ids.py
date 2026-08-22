"""Hub pause controls keep dashboard-stable entity_ids."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.furbulous.registry import (
    _HUB_DESIRED_ENTITY_IDS,
    async_ensure_hub_pause_entity_ids,
)


def test_hub_desired_ids_match_dashboard():
    assert _HUB_DESIRED_ENTITY_IDS["pause_polling"] == "button.furbulous_pause_polling"
    assert (
        _HUB_DESIRED_ENTITY_IDS["pause_polling_1_hour"]
        == "button.furbulous_pause_polling_1_hour"
    )
    assert _HUB_DESIRED_ENTITY_IDS["resume_polling"] == "button.furbulous_resume_polling"
    assert _HUB_DESIRED_ENTITY_IDS["polling_status"] == "sensor.furbulous_cloud_polling"
    assert (
        _HUB_DESIRED_ENTITY_IDS["polling_paused"]
        == "binary_sensor.furbulous_cloud_polling_paused"
    )


@pytest.mark.asyncio
async def test_ensure_hub_renames_mismatched_entity():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "01ABC"

    bad = MagicMock()
    bad.unique_id = "furbulous_hub_01ABC_pause_polling"
    bad.entity_id = "button.furbulous_steve_pause_polling"

    registry = MagicMock()
    device_reg = MagicMock()
    device_reg.async_get_device.return_value = None

    with (
        patch(
            "custom_components.furbulous.registry.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.furbulous.registry.er.async_entries_for_config_entry",
            return_value=[bad],
        ),
        patch(
            "homeassistant.helpers.device_registry.async_get",
            return_value=device_reg,
        ),
    ):
        renamed = await async_ensure_hub_pause_entity_ids(hass, entry)

    assert renamed == 1
    registry.async_update_entity.assert_called_once_with(
        "button.furbulous_steve_pause_polling",
        new_entity_id="button.furbulous_pause_polling",
    )
