"""Tests for region registry."""
from __future__ import annotations

import pytest

from custom_components.furbulous.regions import (
    REGIONS,
    get_region,
    region_for_country,
)


def test_us_not_experimental():
    """US is the supported region."""
    assert REGIONS["us"].experimental is False
    assert REGIONS["us"].iso == "US"
    assert REGIONS["us"].area == "US"


def test_eu_and_asia_experimental():
    """Non-US regions are experimental."""
    assert REGIONS["eu"].experimental is True
    assert REGIONS["asia"].experimental is True


def test_eu_matches_upstream_iso():
    """EU login fields match original upstream (iso=DE, area=EU)."""
    eu = get_region("eu")
    assert eu.iso == "DE"
    assert eu.area == "EU"
    assert "fr.furbulouspet.com" in eu.base_url


def test_region_for_country_mapping():
    """Country codes map to cloud regions."""
    assert region_for_country("US") == "us"
    assert region_for_country("ca") == "us"
    assert region_for_country("DE") == "eu"
    assert region_for_country("GB") == "eu"
    assert region_for_country("JP") == "asia"
    assert region_for_country("ZZ") is None
    assert region_for_country(None) is None


def test_get_region_unknown_raises():
    """Invalid region id raises KeyError."""
    with pytest.raises(KeyError):
        get_region("mars")
