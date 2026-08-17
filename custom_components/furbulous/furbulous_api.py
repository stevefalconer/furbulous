"""Async API client for Furbulous cloud (aiohttp, region-aware).

Blocking: none. All I/O is await aiohttp. asyncio.sleep is used for backoff
(yields the event loop). hashlib.md5 / time.time are O(1) CPU and safe inline.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_APPID,
    API_AUTH_ENDPOINT,
    API_DEVICE_LIST_ENDPOINT,
    API_USER_AGENT,
    API_VERSION,
    PET_LIST_MIN_INTERVAL_SECONDS,
)
from .regions import FurbulousRegion, get_region

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)
_AUTH_TIMEOUT = aiohttp.ClientTimeout(total=10)
_MAX_RETRIES = 3


class FurbulousCatAuthError(Exception):
    """Authentication failed (bad credentials or wrong region)."""


class FurbulousCatConnectionError(Exception):
    """Network or transport failure reaching the Furbulous cloud."""


class FurbulousCatAPI:
    """One shared async client per config entry (session injected by HA)."""

    def __init__(
        self,
        email: str,
        password: str,
        region_id: str = "us",
        account_type: int = 1,
        token: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize for one cloud region.

        Prefer ``async_get_clientsession(hass)`` so the session is shared and
        not closed by this integration.
        """
        self.email = email
        self.password = password
        self.account_type = account_type
        self.region_id = region_id
        self.region: FurbulousRegion = get_region(region_id)
        self.token = token
        self.identity_id: str | None = None
        # Last known device ids for presence polls (bounded: one list snapshot)
        self._known_devices: list[dict[str, Any]] = []
        # Pet roster cache (1 min cadence — roster changes rarely)
        self._cached_pets: list[dict[str, Any]] = []
        self._last_pets_fetch_mono: float = 0.0

        self._session = session
        self._owns_session = session is None

    @property
    def base_url(self) -> str:
        """Cloud base URL for the configured region."""
        return self.region.base_url

    @property
    def known_devices(self) -> list[dict[str, Any]]:
        """Shallow copy of last device identity list (id, iotid, name)."""
        return list(self._known_devices)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return the active session, creating a private one only if needed."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def async_close(self) -> None:
        """Close a privately owned session (no-op for shared HA sessions)."""
        if (
            self._owns_session
            and self._session is not None
            and not self._session.closed
        ):
            await self._session.close()
            self._session = None

    def _generate_sign(self, timestamp: int, path: str) -> str:
        """MD5(appid + url_path + timestamp) — cheap, runs on the loop."""
        data = f"{API_APPID}{path}{timestamp}"
        return hashlib.md5(data.encode()).hexdigest()

    def _auth_headers(self, path: str) -> dict[str, str]:
        """Headers for login (no authorization token)."""
        timestamp = int(time.time())
        return {
            "Content-Type": "application/json",
            "appid": API_APPID,
            "version": API_VERSION,
            "accept": "*/*",
            "accept-language": self.region.accept_language,
            "platform": "ios",
            "user-agent": API_USER_AGENT,
            "ts": str(timestamp),
            "sign": self._generate_sign(timestamp, path),
        }

    def _request_headers(self, path: str) -> dict[str, str]:
        """Headers for authenticated requests."""
        timestamp = int(time.time())
        return {
            "Content-Type": "application/json",
            "appid": API_APPID,
            "accept": "*/*",
            "version": API_VERSION,
            "authorization": self.token or "",
            "accept-language": self.region.accept_language,
            "platform": "ios",
            "user-agent": API_USER_AGENT,
            "ts": str(timestamp),
            "sign": self._generate_sign(timestamp, path),
        }

    async def authenticate(self) -> bool:
        """Authenticate with the Furbulous API for this region."""
        url = f"{self.base_url}{API_AUTH_ENDPOINT}"
        payload = {
            "iso": self.region.iso,
            "area": self.region.area,
            "account_type": self.account_type,
            "clientid": "65l32f6ql1qehx6",
            "brand": "HomeAssistant",
            "client_token": "",
            "password": self.password,
            "AppVersion": "HomeAssistant_1.0.0",
            "account": self.email,
        }
        headers = self._auth_headers(API_AUTH_ENDPOINT)
        session = await self._get_session()

        _LOGGER.debug(
            "Auth start region=%s host=%s experimental=%s",
            self.region_id,
            self.region.base_url,
            self.region.experimental,
        )

        try:
            async with session.post(
                url, json=payload, headers=headers, timeout=_AUTH_TIMEOUT
            ) as response:
                if response.status >= 500:
                    text = await response.text()
                    raise FurbulousCatConnectionError(
                        f"Server error {response.status}: {text[:200]}"
                    )

                try:
                    data = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    text = await response.text()
                    if response.status == 401:
                        raise FurbulousCatAuthError(
                            "Authentication failed: HTTP 401"
                        ) from err
                    raise FurbulousCatConnectionError(
                        f"Invalid auth response: {text[:200]}"
                    ) from err

                if data.get("code") != 0:
                    raise FurbulousCatAuthError(
                        f"Authentication failed: {data.get('message')}"
                    )

                auth_data = data.get("data", {}) or {}
                self.token = auth_data.get("token")
                self.identity_id = auth_data.get("identityid")

                if not self.token:
                    raise FurbulousCatAuthError("No token received from API")

                # One INFO on successful login — not every poll
                _LOGGER.info(
                    "Authenticated with Furbulous (region=%s)", self.region_id
                )
                return True

        except FurbulousCatAuthError:
            raise
        except FurbulousCatConnectionError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug(
                "Auth connection error region=%s: %s", self.region_id, err
            )
            raise FurbulousCatConnectionError(
                f"Authentication request failed: {err}"
            ) from err

    # Vendor auth-failure codes (re-login). Do not treat every "expired"/"token"
    # substring as auth failure — that re-logins and can kick the phone app.
    _TOKEN_FAIL_CODES = frozenset({401, 403, 10401, 10402, 10403})

    def _is_token_error(self, error_code: Any, error_message: str) -> bool:
        """True only for explicit auth/token failure (then we login once more)."""
        if error_code in self._TOKEN_FAIL_CODES:
            return True
        msg = (error_message or "").lower()
        if not msg:
            return False
        mentions_auth = any(
            word in msg for word in ("token", "unauthor", "未授权", "无效的")
        )
        if not mentions_auth:
            return False
        return any(
            word in msg
            for word in ("invalid", "expired", "unauthor", "expire", "无效", "过期")
        )

    async def _make_authenticated_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Authenticated request with timeout and exponential backoff."""
        if not self.token:
            await self.authenticate()

        url = f"{self.base_url}{endpoint}"
        base_endpoint = endpoint.split("?")[0]
        headers = self._request_headers(base_endpoint)
        session = await self._get_session()

        try:
            async with session.request(
                method,
                url,
                headers=headers,
                json=data if method in ("POST", "PUT") else None,
                timeout=_DEFAULT_TIMEOUT,
            ) as response:
                if response.status == 401 and retry_count < _MAX_RETRIES:
                    self.token = None
                    await self.authenticate()
                    await asyncio.sleep(2**retry_count)
                    return await self._make_authenticated_request(
                        endpoint, method, data, retry_count + 1
                    )

                try:
                    result = await response.json(content_type=None)
                except aiohttp.ContentTypeError:
                    text = await response.text()
                    if response.status >= 400:
                        raise FurbulousCatConnectionError(
                            f"HTTP {response.status}: {text[:200]}"
                        )
                    raise FurbulousCatConnectionError(
                        f"Invalid JSON response: {text[:200]}"
                    )

                if result.get("code") != 0:
                    error_message = str(result.get("message", ""))
                    error_code = result.get("code")
                    _LOGGER.debug(
                        "API code=%s message=%s endpoint=%s",
                        error_code,
                        error_message,
                        base_endpoint,
                    )
                    if (
                        self._is_token_error(error_code, error_message)
                        and retry_count < _MAX_RETRIES
                    ):
                        self.token = None
                        await self.authenticate()
                        await asyncio.sleep(2**retry_count)
                        return await self._make_authenticated_request(
                            endpoint, method, data, retry_count + 1
                        )

                return result

        except FurbulousCatAuthError:
            raise
        except FurbulousCatConnectionError:
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            if retry_count < _MAX_RETRIES:
                await asyncio.sleep(2**retry_count)
                return await self._make_authenticated_request(
                    endpoint, method, data, retry_count + 1
                )
            raise FurbulousCatConnectionError(str(err)) from err

    @staticmethod
    def _extract_properties(raw: dict[str, Any]) -> dict[str, Any]:
        """Flatten {key: {value, time}} → {key: value}."""
        extracted: dict[str, Any] = {}
        for key, prop_data in raw.items():
            if isinstance(prop_data, dict) and "value" in prop_data:
                extracted[key] = prop_data["value"]
            else:
                extracted[key] = prop_data
        return extracted

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of Furbulous devices (identity metadata only)."""
        result = await self._make_authenticated_request(API_DEVICE_LIST_ENDPOINT)
        if result.get("code") == 0:
            devices_data = result.get("data", [])
            devices = devices_data if isinstance(devices_data, list) else []
            # Bounded identity cache for presence polls
            self._known_devices = [
                {
                    "id": d.get("id"),
                    "iotid": d.get("iotid"),
                    "name": d.get("name"),
                    "device_online": d.get("device_online"),
                    "product_name": d.get("product_name"),
                    "active_time": d.get("active_time"),
                    "is_disturb": d.get("is_disturb"),
                    "version": d.get("version"),
                }
                for d in devices
                if d.get("iotid")
            ]
            _LOGGER.debug("Device list count=%s", len(self._known_devices))
            return devices
        _LOGGER.debug("Device list failed: %s", result.get("message"))
        return []

    async def get_device_properties(self, iotid: str) -> dict[str, Any]:
        """Get properties for one device (single HTTP call; vendor returns all)."""
        try:
            endpoint = f"/app/v1/device/properties/get?iotid={iotid}"
            result = await self._make_authenticated_request(endpoint)
            if result.get("code") == 0:
                return self._extract_properties(result.get("data", {}) or {})
            _LOGGER.debug(
                "Properties failed iotid=%s: %s", iotid, result.get("message")
            )
            return {}
        except (FurbulousCatAuthError, FurbulousCatConnectionError):
            raise
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Properties error iotid=%s: %s", iotid, err)
            return {}

    async def get_device_daily_stats(self, iotid: str) -> dict[str, Any]:
        """Get daily statistics (wcheader) for one device."""
        try:
            endpoint = f"/app/v1/device/data/wcheader?iotid={iotid}"
            result = await self._make_authenticated_request(endpoint)
            if result.get("code") == 0:
                return result.get("data", {}) or {}
            return {}
        except (FurbulousCatAuthError, FurbulousCatConnectionError):
            raise
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Daily stats error iotid=%s: %s", iotid, err)
            return {}

    async def get_device_wc_history(self, iotid: str) -> list[dict[str, Any]]:
        """Visit activity list: start_time, weight (g), duration — no pet names.

        Verified endpoint: GET /app/v1/device/data/wc?iotid=
        """
        try:
            endpoint = f"/app/v1/device/data/wc?iotid={iotid}"
            result = await self._make_authenticated_request(endpoint)
            if result.get("code") != 0:
                return []
            data = result.get("data")
            return data if isinstance(data, list) else []
        except (FurbulousCatAuthError, FurbulousCatConnectionError):
            raise
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("WC history error iotid=%s: %s", iotid, err)
            return []

    async def set_device_property(
        self, iotid: str, properties: dict[str, Any]
    ) -> bool:
        """Set device properties via properties/set (user action, not poll)."""
        try:
            endpoint = "/app/v1/device/properties/set"
            payload = {"iotid": iotid, "items": properties}
            result = await self._make_authenticated_request(
                endpoint, method="POST", data=payload
            )
            if result.get("code") == 0:
                _LOGGER.debug(
                    "Set properties iotid=%s keys=%s",
                    iotid,
                    list(properties.keys()),
                )
                return True
            _LOGGER.warning(
                "Failed to set properties iotid=%s code=%s",
                iotid,
                result.get("code"),
            )
            return False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Error setting properties iotid=%s: %s", iotid, err)
            return False

    async def set_device_disturb(self, iotid: str, is_disturb: bool) -> bool:
        """Set Do Not Disturb mode (user action)."""
        try:
            endpoint = "/app/v1/device/disturb"
            payload = {"iotid": iotid, "is_disturb": 1 if is_disturb else 0}
            result = await self._make_authenticated_request(
                endpoint, method="PUT", data=payload
            )
            if result.get("code") == 0:
                _LOGGER.debug("Set DND iotid=%s value=%s", iotid, is_disturb)
                return True
            _LOGGER.warning("Failed to set DND iotid=%s", iotid)
            return False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Error setting DND iotid=%s: %s", iotid, err)
            return False

    async def get_pets(self, *, force: bool = False) -> list[dict[str, Any]]:
        """Fetch pet roster with a 1-minute minimum interval (unless force).

        Roster names change rarely. Visit identity/weight come from
        ``properties/get`` on the 30s path — do not require pet/list that often.
        """
        now = time.monotonic()
        if (
            not force
            and self._cached_pets is not None
            and (now - self._last_pets_fetch_mono) < PET_LIST_MIN_INTERVAL_SECONDS
            and self._last_pets_fetch_mono > 0
        ):
            return list(self._cached_pets)

        try:
            result = await self._make_authenticated_request("/app/v1/pet/list")
            if result.get("code") != 0:
                return list(self._cached_pets)
            data = result.get("data")
            pets: list[dict[str, Any]] = []
            if isinstance(data, list):
                pets = data
            elif isinstance(data, dict):
                raw = data.get("list") or data.get("pets") or data.get("data")
                if isinstance(raw, list):
                    pets = raw
            self._cached_pets = pets
            self._last_pets_fetch_mono = now
            return list(pets)
        except (FurbulousCatAuthError, FurbulousCatConnectionError):
            raise
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Pet list error: %s", err)
            return list(self._cached_pets)

    async def async_get_full_snapshot(self) -> dict[str, Any]:
        """Full poll: device list + properties + daily stats + pets.

        Snapshot is current state only — history lives in the local analytics store.
        """
        start = time.monotonic()
        devices = await self.get_devices()
        enriched: list[dict[str, Any]] = []
        for device in devices:
            iotid = device.get("iotid")
            if iotid:
                device = dict(device)
                device["properties"] = await self.get_device_properties(iotid)
                device["daily_stats"] = await self.get_device_daily_stats(iotid)
                # Activity for Last cat / analytics (no pet names on records)
                device["wc_history"] = await self.get_device_wc_history(iotid)
            enriched.append(device)

        pets = await self.get_pets(force=True)

        elapsed_ms = (time.monotonic() - start) * 1000
        _LOGGER.debug(
            "Full snapshot devices=%s pets=%s elapsed_ms=%.0f",
            len(enriched),
            len(pets),
            elapsed_ms,
        )
        return {
            "authenticated": True,
            "identity_id": self.identity_id,
            "region": self.region_id,
            "devices": enriched,
            "pets": pets,
        }

    async def async_get_presence_snapshot(self) -> dict[str, Any]:
        """Light poll (~30s): properties for known devices; pets ≤1/min.

        Properties include occupancy, weight, errors, and pet-identity fields —
        that single call is the high-value fast path.

        Pet roster is throttled to ``PET_LIST_MIN_INTERVAL_SECONDS`` (60s).
        Skips device list and daily stats (5 min full poll only).
        """
        start = time.monotonic()
        devices_out: list[dict[str, Any]] = []
        for meta in self._known_devices:
            iotid = meta.get("iotid")
            if not iotid:
                continue
            props = await self.get_device_properties(iotid)
            devices_out.append(
                {
                    "id": meta.get("id"),
                    "iotid": iotid,
                    "name": meta.get("name"),
                    "properties": props,
                }
            )

        # Cached if fetched within the last minute (no extra HTTP)
        pets = await self.get_pets(force=False)

        elapsed_ms = (time.monotonic() - start) * 1000
        _LOGGER.debug(
            "Presence snapshot devices=%s pets=%s elapsed_ms=%.0f",
            len(devices_out),
            len(pets),
            elapsed_ms,
        )
        return {"devices": devices_out, "pets": pets}
