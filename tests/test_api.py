"""Async API client tests with a fake aiohttp session (no live network)."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.furbulous.const import (
    API_APPID,
    API_AUTH_ENDPOINT,
    PRESENCE_PROPS_MAX_AGE_S,
)
from custom_components.furbulous.furbulous_api import (
    FurbulousCatAPI,
    FurbulousCatAuthError,
    FurbulousCatConnectionError,
)
from custom_components.furbulous.regions import get_region

US_BASE = "https://app.api.us.furbulouspet.com:1443"


class FakeResponse:
    """Minimal async context-manager response."""

    def __init__(
        self,
        status: int = 200,
        payload: dict | None = None,
        text: str = "",
    ) -> None:
        self.status = status
        self._payload = payload
        self._text = text or (
            json.dumps(payload) if payload is not None else ""
        )

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self, content_type: str | None = None) -> Any:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    async def text(self) -> str:
        return self._text


class FakeSession:
    """Records requests and returns scripted responses in order per method+url."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._queue: dict[tuple[str, str], list[FakeResponse]] = {}
        self.closed = False

    def add(
        self,
        method: str,
        url: str,
        *,
        status: int = 200,
        payload: dict | None = None,
        text: str = "",
    ) -> None:
        key = (method.upper(), url)
        self._queue.setdefault(key, []).append(
            FakeResponse(status=status, payload=payload, text=text)
        )

    def _next(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method.upper(), "url": url, **kwargs})
        key = (method.upper(), url)
        queue = self._queue.get(key)
        if not queue:
            raise AssertionError(f"Unexpected request {method} {url}")
        return queue.pop(0)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._next("POST", url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._next("GET", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._next("PUT", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        return self._next(method, url, **kwargs)


def _expected_sign(path: str, ts: int) -> str:
    return hashlib.md5(f"{API_APPID}{path}{ts}".encode()).hexdigest()


@pytest.mark.asyncio
async def test_authenticate_success(sample_auth_success):
    """Successful login stores token and identity."""
    session = FakeSession()
    session.add(
        "POST",
        f"{US_BASE}{API_AUTH_ENDPOINT}",
        payload=sample_auth_success,
    )
    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    assert await api.authenticate() is True
    assert api.token == "test-token-abc123"
    assert api.identity_id == "identity-99"


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials(sample_auth_failure):
    """Vendor code != 0 becomes FurbulousCatAuthError."""
    session = FakeSession()
    session.add(
        "POST",
        f"{US_BASE}{API_AUTH_ENDPOINT}",
        payload=sample_auth_failure,
    )
    api = FurbulousCatAPI(
        email="bad@example.com",
        password="wrong",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    with pytest.raises(FurbulousCatAuthError, match="invalid account"):
        await api.authenticate()


@pytest.mark.asyncio
async def test_authenticate_server_error_is_connection():
    """HTTP 5xx becomes connection error, not auth."""
    session = FakeSession()
    session.add(
        "POST",
        f"{US_BASE}{API_AUTH_ENDPOINT}",
        status=503,
        text="unavailable",
    )
    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    with pytest.raises(FurbulousCatConnectionError):
        await api.authenticate()


@pytest.mark.asyncio
async def test_authenticate_uses_region_iso_area(sample_auth_success):
    """Login body must include region iso/area."""
    session = FakeSession()
    session.add(
        "POST",
        f"{US_BASE}{API_AUTH_ENDPOINT}",
        payload=sample_auth_success,
    )
    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.authenticate()
    body = session.calls[-1]["json"]
    assert body["iso"] == "US"
    assert body["area"] == "US"
    assert body["account"] == "user@example.com"
    assert body["password"] == "secret"


@pytest.mark.asyncio
async def test_eu_region_hits_eu_host(sample_auth_success):
    """EU region uses Frankfurt-style host from registry."""
    eu = get_region("eu")
    session = FakeSession()
    session.add(
        "POST",
        f"{eu.base_url}{API_AUTH_ENDPOINT}",
        payload=sample_auth_success,
    )
    api = FurbulousCatAPI(
        email="eu@example.com",
        password="secret",
        region_id="eu",
        session=session,  # type: ignore[arg-type]
    )
    await api.authenticate()
    assert api.region.iso == "DE"
    assert api.region.area == "EU"
    assert session.calls[-1]["url"].startswith(eu.base_url)


def _count_url(calls: list[dict], needle: str) -> int:
    return sum(1 for c in calls if needle in c["url"])


@pytest.mark.asyncio
async def test_full_snapshot_pipeline(
    sample_auth_success,
    sample_device_list,
    sample_properties_grams,
    sample_daily_stats,
):
    """Full snapshot: list + cached presence props + stats + pets (no props GET)."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.get_devices()
    await api.async_get_presence_snapshot()
    calls_before_full = len(session.calls)
    data = await api.async_get_full_snapshot()

    assert data["authenticated"] is True
    assert data["identity_id"] == "identity-99"
    assert data["region"] == "us"
    assert data["pets"] == [{"id": 1, "name": "Mochi"}]
    assert len(data["devices"]) == 1
    device = data["devices"][0]
    assert device["properties"]["catWeight"] == 4500
    assert device.get("props_stale") is not True
    assert device["daily_stats"]["times"] == 7
    assert len(api.known_devices) == 1
    full_calls = session.calls[calls_before_full:]
    assert _count_url(full_calls, "properties/get") == 0
    assert _count_url(full_calls, "wcheader") == 1
    assert _count_url(full_calls, "/device/data/wc?") == 1
    assert _count_url(full_calls, "pet/list") == 0


@pytest.mark.asyncio
async def test_full_snapshot_zero_props_get_when_cache_fresh(
    sample_auth_success,
    sample_device_list,
    sample_properties_grams,
    sample_daily_stats,
):
    """Option A: fresh presence cache → full issues zero properties/get."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.get_devices()
    presence = await api.async_get_presence_snapshot()
    assert _count_url(session.calls, "properties/get") == 1

    data = await api.async_get_full_snapshot(
        prior_devices=presence.get("devices")
    )
    assert data["devices"][0]["properties"]["catWeight"] == 4500
    assert _count_url(session.calls, "properties/get") == 1


@pytest.mark.asyncio
async def test_full_snapshot_stale_reuses_prior_without_get(
    sample_auth_success,
    sample_device_list,
    sample_daily_stats,
):
    """Stale/missing cache reuses prior_devices props; never properties/get."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    prior = [
        {
            "id": 42,
            "iotid": iotid,
            "properties": {"catWeight": 4100, "workstatus": 0},
            "property_times": {"catWeight": 1700000000.0},
        }
    ]
    data = await api.async_get_full_snapshot(prior_devices=prior)
    device = data["devices"][0]
    assert device["properties"]["catWeight"] == 4100
    assert device["props_stale"] is True
    assert device["property_times"]["catWeight"] == 1700000000.0
    assert _count_url(session.calls, "properties/get") == 0


@pytest.mark.asyncio
async def test_full_snapshot_aged_cache_reuses_prior_without_get(
    sample_auth_success,
    sample_device_list,
    sample_daily_stats,
):
    """Cache entry older than PRESENCE_PROPS_MAX_AGE_S reuses prior, no GET."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    api._presence_props_cache[iotid] = {
        "properties": {"catWeight": 999},
        "property_times": {},
        "mono_ts": time.monotonic() - (PRESENCE_PROPS_MAX_AGE_S + 1.0),
        "device_id": 42,
    }
    prior = [
        {
            "id": 42,
            "iotid": iotid,
            "properties": {"catWeight": 4100, "workstatus": 0},
            "property_times": {"catWeight": 1700000000.0},
        }
    ]
    data = await api.async_get_full_snapshot(prior_devices=prior)
    device = data["devices"][0]
    assert device["properties"]["catWeight"] == 4100
    assert device["props_stale"] is True
    assert _count_url(session.calls, "properties/get") == 0


@pytest.mark.asyncio
async def test_full_snapshot_empty_fresh_cache_prefers_prior(
    sample_auth_success,
    sample_device_list,
    sample_daily_stats,
):
    """Fresh cache with empty properties falls back to prior_devices."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    api._presence_props_cache[iotid] = {
        "properties": {},
        "property_times": {},
        "mono_ts": time.monotonic(),
        "device_id": 42,
    }
    prior = [
        {
            "id": 42,
            "iotid": iotid,
            "properties": {"catWeight": 4100},
            "property_times": {},
        }
    ]
    data = await api.async_get_full_snapshot(prior_devices=prior)
    assert data["devices"][0]["properties"]["catWeight"] == 4100
    assert data["devices"][0]["props_stale"] is True
    assert _count_url(session.calls, "properties/get") == 0


@pytest.mark.asyncio
async def test_presence_skips_publishing_empty_props(
    sample_auth_success,
    sample_device_list,
):
    """Soft-fail empty properties/get must not overwrite a warm cache entry."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload={"code": 1, "message": "fail", "data": {}},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": []}},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    api._presence_props_cache[iotid] = {
        "properties": {"catWeight": 4500},
        "property_times": {},
        "mono_ts": time.monotonic(),
        "device_id": 42,
    }
    await api.get_devices()
    await api.async_get_presence_snapshot()
    assert api._presence_props_cache[iotid]["properties"]["catWeight"] == 4500


@pytest.mark.asyncio
async def test_startup_order_presence_before_full_has_props(
    sample_auth_success,
    sample_device_list,
    sample_properties_grams,
    sample_daily_stats,
):
    """Setup-like order (devices→presence→full) leaves full devices with props."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.get_devices()
    presence = await api.async_get_presence_snapshot()
    assert presence["devices"][0]["properties"]["catWeight"] == 4500
    full = await api.async_get_full_snapshot(prior_devices=None)
    assert full["devices"][0]["properties"]["catWeight"] == 4500
    assert full["devices"][0].get("props_stale") is not True
    assert _count_url(session.calls, "properties/get") == 1


@pytest.mark.asyncio
async def test_presence_snapshot_skips_list_and_stats(
    sample_auth_success,
    sample_device_list,
    sample_properties_grams,
    sample_daily_stats,
):
    """Presence poll only hits properties for known iotids."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )
    # Presence: properties only (pet/list throttled / cached)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.async_get_full_snapshot()
    calls_after_full = len(session.calls)

    presence = await api.async_get_presence_snapshot()
    assert len(presence["devices"]) == 1
    assert presence["devices"][0]["properties"]["workstatus"] == 0
    # Pets returned from daily cache (no second pet/list HTTP)
    assert presence["pets"][0]["name"] == "Mochi"

    new_calls = session.calls[calls_after_full:]
    assert len(new_calls) == 1
    assert "properties/get" in new_calls[0]["url"]
    assert all("pet/list" not in c["url"] for c in new_calls)
    assert all("wcheader" not in c["url"] for c in new_calls)
    assert all("device/list" not in c["url"] for c in new_calls)
    assert iotid in api._presence_props_cache


@pytest.mark.asyncio
async def test_pet_list_not_fetched_twice_within_24h(
    sample_auth_success,
    sample_device_list,
    sample_properties_grams,
    sample_daily_stats,
):
    """pet/list is shared across presence+full and not forced on full."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.get_devices()
    presence = await api.async_get_presence_snapshot()
    assert presence["pets"][0]["name"] == "Mochi"
    assert _count_url(session.calls, "pet/list") == 1

    full = await api.async_get_full_snapshot(prior_devices=presence["devices"])
    assert full["pets"][0]["name"] == "Mochi"
    assert _count_url(session.calls, "pet/list") == 1

    # Resume-style second presence must not stampede pet/list
    presence2 = await api.async_get_presence_snapshot()
    assert presence2["pets"][0]["name"] == "Mochi"
    assert _count_url(session.calls, "pet/list") == 1


@pytest.mark.asyncio
async def test_pet_list_refetches_after_daily_window(
    sample_auth_success,
    sample_device_list,
    sample_properties_grams,
    sample_daily_stats,
):
    """pet/list is allowed again after the 24 h throttle window."""
    iotid = "iot-device-001"
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add("GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list)
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wcheader?iotid={iotid}",
        payload=sample_daily_stats,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/data/wc?iotid={iotid}",
        payload={"code": 0, "data": []},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi"}]}},
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/properties/get?iotid={iotid}",
        payload=sample_properties_grams,
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/pet/list",
        payload={"code": 0, "data": {"list": [{"id": 1, "name": "Mochi2"}]}},
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.async_get_full_snapshot()
    # Expire pet cache (simulate >24 h)
    api._last_pets_fetch_mono = 0.0
    presence = await api.async_get_presence_snapshot()
    assert presence["pets"][0]["name"] == "Mochi2"


@pytest.mark.asyncio
async def test_set_device_property_posts_items(sample_auth_success):
    """Property set uses items envelope."""
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add(
        "POST",
        f"{US_BASE}/app/v1/device/properties/set",
        payload={"code": 0, "message": "ok"},
    )
    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.authenticate()
    ok = await api.set_device_property("iot-1", {"handMode": 1})
    assert ok is True
    set_call = [c for c in session.calls if c["url"].endswith("/properties/set")][-1]
    assert set_call["json"] == {"iotid": "iot-1", "items": {"handMode": 1}}
    assert set_call["method"] == "POST"


@pytest.mark.asyncio
async def test_signature_matches_app_algorithm():
    """Sign is MD5(appid + path + timestamp)."""
    api = FurbulousCatAPI(email="x", password="y", region_id="us")
    ts = 1700000000
    path = "/app/v1/auth/login"
    assert api._generate_sign(ts, path) == _expected_sign(path, ts)
    await api.async_close()


@pytest.mark.asyncio
async def test_token_refresh_on_10403(
    sample_auth_success,
    sample_device_list,
):
    """Invalid token code triggers re-auth and retry."""
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add(
        "GET",
        f"{US_BASE}/app/v1/device/list",
        payload={"code": 10403, "message": "Invalid Token"},
    )
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add(
        "GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list
    )

    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    # Speed up retry sleep
    import custom_components.furbulous.furbulous_api as api_mod

    original_sleep = api_mod.asyncio.sleep
    api_mod.asyncio.sleep = AsyncMock()  # type: ignore[assignment]
    try:
        devices = await api.get_devices()
    finally:
        api_mod.asyncio.sleep = original_sleep

    assert len(devices) == 1
    assert devices[0]["iotid"] == "iot-device-001"


def test_token_error_only_on_explicit_auth_failure():
    """Do not re-login on unrelated 'expired' / 'token' substrings."""
    api = FurbulousCatAPI(email="x", password="y", region_id="us")
    assert api._is_token_error(10403, "") is True
    assert api._is_token_error(0, "Invalid Token") is True
    assert api._is_token_error(0, "token expired") is True
    assert api._is_token_error(0, "unauthorized") is True
    assert api._is_token_error(0, "bag expired") is False
    assert api._is_token_error(0, "timing token field") is False


@pytest.mark.asyncio
async def test_reuse_token_without_second_login(
    sample_auth_success, sample_device_list
):
    """One login, then Bearer token on later calls (no per-request login)."""
    session = FakeSession()
    session.add(
        "POST", f"{US_BASE}{API_AUTH_ENDPOINT}", payload=sample_auth_success
    )
    session.add(
        "GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list
    )
    session.add(
        "GET", f"{US_BASE}/app/v1/device/list", payload=sample_device_list
    )
    api = FurbulousCatAPI(
        email="user@example.com",
        password="secret",
        region_id="us",
        session=session,  # type: ignore[arg-type]
    )
    await api.get_devices()
    await api.get_devices()
    logins = [c for c in session.calls if c["url"].endswith("/auth/login")]
    lists = [c for c in session.calls if c["url"].endswith("/device/list")]
    assert len(logins) == 1
    assert len(lists) == 2
