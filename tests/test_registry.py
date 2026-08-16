"""Tests for entity registry display-override cleanup."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.furbulous.registry import (
    _is_weight_entity,
    async_clear_display_overrides,
)


def test_is_weight_entity_detects_cat_weight():
    """Unique id markers identify weight sensors."""
    entry = SimpleNamespace(domain="sensor", unique_id="furbulous_42_catWeight")
    assert _is_weight_entity(entry) is True
    entry2 = SimpleNamespace(domain="sensor", unique_id="furbulous_42_daily_times")
    assert _is_weight_entity(entry2) is False
    entry3 = SimpleNamespace(domain="binary_sensor", unique_id="furbulous_42_catWeight")
    assert _is_weight_entity(entry3) is False


@pytest.mark.asyncio
async def test_clear_display_overrides_clears_unit_and_name(monkeypatch):
    """Reconfigure path clears custom name and sensor unit options."""
    from custom_components.furbulous import registry as reg_mod

    weight_entry = SimpleNamespace(
        entity_id="sensor.box_cat_weight",
        domain="sensor",
        platform="furbulous",
        config_entry_id="entry-1",
        unique_id="furbulous_42_catWeight",
        name="Poids du chat",  # sticky French custom name
        has_entity_name=False,
        unit_of_measurement="g",
        options={
            "sensor": {
                "unit_of_measurement": "kg",
                "suggested_unit_of_measurement": "kg",
            }
        },
    )
    other_entry = SimpleNamespace(
        entity_id="sensor.box_daily_uses",
        domain="sensor",
        platform="furbulous",
        config_entry_id="entry-1",
        unique_id="furbulous_42_daily_times",
        name=None,
        has_entity_name=True,
        unit_of_measurement=None,
        options={"sensor": {}},
    )

    mock_registry = MagicMock()
    mock_registry.async_update_entity = MagicMock()
    mock_registry.async_update_entity_options = MagicMock()

    monkeypatch.setattr(
        reg_mod.er,
        "async_get",
        lambda hass: mock_registry,
    )
    monkeypatch.setattr(
        reg_mod.er,
        "async_entries_for_config_entry",
        lambda registry, entry_id: [weight_entry, other_entry],
    )

    config_entry = SimpleNamespace(entry_id="entry-1")
    count = await async_clear_display_overrides(
        hass=MagicMock(),
        config_entry=config_entry,
        clear_custom_names=True,
        weight_units_only=False,
    )

    assert count >= 1
    # Weight entity: name + unit cleared
    mock_registry.async_update_entity.assert_any_call(
        "sensor.box_cat_weight",
        name=None,
        has_entity_name=True,
        unit_of_measurement=None,
    )
    mock_registry.async_update_entity_options.assert_any_call(
        "sensor.box_cat_weight",
        "sensor",
        {},
    )
    # Weight sensors force private refresh so suggested unit (lb) re-applies
    mock_registry.async_update_entity_options.assert_any_call(
        "sensor.box_cat_weight",
        "sensor.private",
        {"refresh_initial_entity_options": True},
    )


@pytest.mark.asyncio
async def test_clear_weight_units_only_skips_names(monkeypatch):
    """Upgrade one-shot only touches weight unit locks."""
    from custom_components.furbulous import registry as reg_mod

    weight_entry = SimpleNamespace(
        entity_id="sensor.box_cat_weight",
        domain="sensor",
        platform="furbulous",
        config_entry_id="entry-1",
        unique_id="furbulous_42_catWeight",
        name="My custom name",
        has_entity_name=True,
        unit_of_measurement=None,
        options={"sensor": {"unit_of_measurement": "lb"}},
    )

    mock_registry = MagicMock()
    mock_registry.async_update_entity = MagicMock()
    mock_registry.async_update_entity_options = MagicMock()

    monkeypatch.setattr(reg_mod.er, "async_get", lambda hass: mock_registry)
    monkeypatch.setattr(
        reg_mod.er,
        "async_entries_for_config_entry",
        lambda registry, entry_id: [weight_entry],
    )

    await async_clear_display_overrides(
        hass=MagicMock(),
        config_entry=SimpleNamespace(entry_id="entry-1"),
        clear_custom_names=False,
        weight_units_only=True,
    )

    # Name must NOT be cleared on upgrade path
    for call in mock_registry.async_update_entity.call_args_list:
        assert "name" not in (call.kwargs or {})
    # Must request refresh of initial suggested unit (lb under US customary)
    mock_registry.async_update_entity_options.assert_any_call(
        "sensor.box_cat_weight",
        "sensor.private",
        {"refresh_initial_entity_options": True},
    )
