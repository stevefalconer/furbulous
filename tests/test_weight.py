"""Tests for cat weight resolution (native grams)."""
from __future__ import annotations

import pytest

from custom_components.furbulous.weight import (
    resolve_cat_weight_grams,
    source_weight_field,
)


def test_resolve_cat_weight_grams_default():
    """Known production field: catWeight in grams."""
    props = {"catWeight": 4500}
    assert resolve_cat_weight_grams(props) == 4500.0
    assert source_weight_field(props) == "catWeight"


def test_resolve_nested_value_dict():
    """Handle unextracted {value, time} property shape."""
    props = {"catWeight": {"value": 3200, "time": 1}}
    assert resolve_cat_weight_grams(props) == 3200.0


def test_resolve_prefers_grams_over_kg():
    """Gram field wins when both present."""
    props = {"catWeight": 4500, "catWeightKg": 9.9}
    assert resolve_cat_weight_grams(props) == 4500.0
    assert source_weight_field(props) == "catWeight"


def test_resolve_kg_normalized_to_grams():
    """Explicit kg field is normalized to grams for native UoM."""
    props = {"catWeightKg": 4.5}
    assert resolve_cat_weight_grams(props) == pytest.approx(4500.0)


def test_resolve_lb_normalized_to_grams():
    """Explicit lb field is normalized to grams for native UoM."""
    props = {"catWeightLb": 10.0}
    assert resolve_cat_weight_grams(props) == pytest.approx(4535.9237)


def test_resolve_missing_returns_none():
    """No weight keys → None."""
    assert resolve_cat_weight_grams({}) is None
    assert resolve_cat_weight_grams(None) is None
    assert source_weight_field({}) is None
