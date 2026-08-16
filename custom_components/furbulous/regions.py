"""Furbulous cloud region registry.

Accounts and devices are region-scoped by the vendor. Wrong region causes
authentication failure even with correct credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FurbulousRegion:
    """Configuration for one Furbulous cloud region."""

    id: str
    base_url: str
    iso: str
    area: str
    accept_language: str
    experimental: bool
    countries: frozenset[str]


# US: maintainer-supported path (verified on this fork).
# EU: from original upstream (iso=DE, area=EU); experimental for this fork.
# Asia: best-effort placeholder host/iso/area; experimental until community confirms.
REGIONS: dict[str, FurbulousRegion] = {
    "us": FurbulousRegion(
        id="us",
        base_url="https://app.api.us.furbulouspet.com:1443",
        iso="US",
        area="US",
        accept_language="en",
        experimental=False,
        countries=frozenset({"US", "CA"}),
    ),
    "eu": FurbulousRegion(
        id="eu",
        base_url="https://app.api.fr.furbulouspet.com:1443",
        iso="DE",
        area="EU",
        accept_language="en",
        experimental=True,
        countries=frozenset(
            {
                "AT",
                "BE",
                "BG",
                "HR",
                "CY",
                "CZ",
                "DK",
                "EE",
                "FI",
                "FR",
                "DE",
                "GR",
                "HU",
                "IE",
                "IT",
                "LV",
                "LT",
                "LU",
                "MT",
                "NL",
                "PL",
                "PT",
                "RO",
                "SK",
                "SI",
                "ES",
                "SE",
                "GB",
            }
        ),
    ),
    "asia": FurbulousRegion(
        id="asia",
        base_url="https://app.api.sg.furbulouspet.com:1443",
        iso="SG",
        area="ASIA",
        accept_language="en",
        experimental=True,
        countries=frozenset({"SG", "JP", "AU", "TW", "HK", "KR", "CN"}),
    ),
}

REGION_IDS: list[str] = list(REGIONS.keys())
DEFAULT_REGION = "us"


def get_region(region_id: str) -> FurbulousRegion:
    """Return region config or raise KeyError."""
    return REGIONS[region_id]


def region_for_country(country: str | None) -> str | None:
    """Map HA ISO country code to a region id, if known."""
    if not country:
        return None
    code = country.upper()
    for region in REGIONS.values():
        if code in region.countries:
            return region.id
    return None


def default_region_for_hass(hass: Any) -> str | None:
    """Suggest a region from Home Assistant country, or None to force choice."""
    country = getattr(getattr(hass, "config", None), "country", None)
    return region_for_country(country)
