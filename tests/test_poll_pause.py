"""Unit tests for cloud polling pause (phone-app friendly)."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.furbulous.poll_pause import (
    MODE_ACTIVE,
    MODE_PAUSED,
    MODE_PAUSED_UNTIL,
    PollPauseController,
)


@pytest.mark.asyncio
async def test_pause_indefinite_and_resume():
    hass = MagicMock()
    hass.async_create_task = MagicMock()
    full = MagicMock()
    full.update_interval = timedelta(minutes=5)
    full.async_request_refresh = AsyncMock()
    presence = MagicMock()
    presence.update_interval = timedelta(seconds=30)
    presence.async_request_refresh = AsyncMock()

    ctrl = PollPauseController(hass, "entry-1", full, presence)
    assert ctrl.mode == MODE_ACTIVE
    assert ctrl.is_paused is False

    await ctrl.async_pause_indefinite()
    assert ctrl.is_paused is True
    assert ctrl.mode == MODE_PAUSED
    assert full.update_interval is None
    assert presence.update_interval is None
    assert "Paused" == ctrl.status_label

    await ctrl.async_resume()
    assert ctrl.is_paused is False
    assert ctrl.mode == MODE_ACTIVE
    assert full.update_interval == timedelta(minutes=5)
    assert presence.update_interval == timedelta(seconds=30)
    presence.async_request_refresh.assert_awaited()
    full.async_request_refresh.assert_awaited()


@pytest.mark.asyncio
async def test_pause_one_hour_schedules_timer(monkeypatch):
    hass = MagicMock()
    scheduled = {}

    def fake_call_later(_hass, seconds, action):
        scheduled["seconds"] = seconds
        scheduled["action"] = action
        return MagicMock()

    monkeypatch.setattr(
        "custom_components.furbulous.poll_pause.async_call_later",
        fake_call_later,
    )

    full = MagicMock()
    presence = MagicMock()
    ctrl = PollPauseController(hass, "entry-2", full, presence)
    await ctrl.async_pause_for(3600)
    assert ctrl.mode == MODE_PAUSED_UNTIL
    assert ctrl.resume_at is not None
    assert scheduled["seconds"] == 3600
    assert "Paused until" in ctrl.status_label
