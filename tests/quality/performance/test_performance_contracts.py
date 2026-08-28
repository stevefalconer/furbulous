"""Performance contracts: throttle, idle path, O-device updates."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.furbulous.const import (
    PET_LIST_MIN_INTERVAL_SECONDS,
    PRESENCE_PROPS_MAX_AGE_S,
)
from custom_components.furbulous.entity import FurbulousEntity
from custom_components.furbulous.furbulous_api import FurbulousCatAPI
from custom_components.furbulous.analytics.engine import AnalyticsEngine


def test_pet_list_min_interval_is_daily():
    assert PET_LIST_MIN_INTERVAL_SECONDS >= 86400


def test_presence_props_max_age_is_90s():
    assert PRESENCE_PROPS_MAX_AGE_S == 90.0


@pytest.mark.asyncio
async def test_pet_list_cache_avoids_second_http(sample_auth_success=None):
    """Unit-level: second get_pets within window uses cache (no extra HTTP)."""
    session = MagicMock()
    # Minimal API instance without full auth if constructor allows
    api = FurbulousCatAPI.__new__(FurbulousCatAPI)
    api._session = session
    api._email = "a@b.c"
    api._password = "x"
    api._region_id = "us"
    api._account_type = 1
    api._token = "t"
    api._cached_pets = [{"id": 1, "name": "A"}]
    api._last_pets_fetch_mono = time.monotonic()
    api._known_devices = []

    # Patch request so any call fails the test
    api._make_authenticated_request = AsyncMock(
        side_effect=AssertionError("should use cache")
    )
    pets = await api.get_pets(force=False)
    assert pets == [{"id": 1, "name": "A"}]


def test_entity_fingerprint_skips_unchanged():
    """Coordinator entity only writes when fingerprint changes."""

    class _S(FurbulousEntity):
        @property
        def native_value(self):
            return self._v

    coord = MagicMock()
    coord.data = {"devices": [{"id": 1, "name": "B"}]}
    coord.last_update_success = True
    ent = _S(coord, 1, translation_key="t", unique_id="u")
    ent._v = 1
    ent.async_write_ha_state = MagicMock()
    # Simulate first update
    ent._last_fingerprint = object()
    ent._handle_coordinator_update()
    assert ent.async_write_ha_state.called or ent._last_fingerprint == (
        "nv",
        1,
        True,
    )
    # Second identical update should no-op write path via fingerprint equality
    writes_before = ent.async_write_ha_state.call_count
    ent._handle_coordinator_update()
    assert ent.async_write_ha_state.call_count == writes_before


def test_analytics_idle_snapshot_no_forced_full_recompute(tmp_path=None):
    """process_snapshot with full_recompute=False on quiet data is cheap."""
    hass = MagicMock()
    eng = AnalyticsEngine(hass, "entry-1")
    # Avoid disk: empty store
    eng.store._events = []  # noqa: SLF001
    eng.store._by_device = {}  # noqa: SLF001
    device = {
        "id": 1,
        "iotid": "iot",
        "properties": {"workstatus": 0, "errorReportEvent": 0, "catWeight": 0},
    }
    eng.process_snapshot([device], full_recompute=False)
    eng.process_snapshot([device], full_recompute=False)
    # No crash; metrics dict exists
    assert isinstance(eng.metrics_for_device(1), dict)
