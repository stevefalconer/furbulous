"""Closest-cat-by-weight matching — realistic multi-cat / multi-box cases."""
from __future__ import annotations

import random

import pytest

from custom_components.furbulous.analytics.pet_match import (
    extract_pet_weight_grams,
    is_plausible_cat_weight,
    match_closest_pet,
    resolve_visit_identity,
    stable_visit_weight_g,
    update_learned_weight,
)

# Five cats (profile kg) — similar to a real multi-cat home
FIVE_CATS = [
    {"id": 1, "name": "Mochi", "weight": 3.2},   # 3200 g
    {"id": 2, "name": "Bean", "weight": 3.9},    # 3900 g
    {"id": 3, "name": "Luna", "weight": 4.6},    # 4600 g
    {"id": 4, "name": "Shadow", "weight": 5.4},  # 5400 g
    {"id": 5, "name": "Pumpkin", "weight": 6.8},  # 6800 g
]


def _g(kg: float) -> float:
    return kg * 1000.0


def test_extract_weight_kg_and_g():
    assert extract_pet_weight_grams({"weight": 4.5}) == pytest.approx(4500.0)
    assert extract_pet_weight_grams({"weightG": 4500}) == pytest.approx(4500.0)
    assert extract_pet_weight_grams({"weightKg": 4.2}) == pytest.approx(4200.0)


def test_match_closest_of_two_cats():
    pets = [
        {"id": 1, "name": "Mochi", "weight": 4.0},
        {"id": 2, "name": "Bean", "weight": 5.5},
    ]
    m = match_closest_pet(4100, pets)
    assert m.pet_name == "Mochi"
    assert m.method == "weight_closest"
    m = match_closest_pet(5400, pets)
    assert m.pet_name == "Bean"


def test_five_cats_with_realistic_fluctuation():
    """Each cat's noisy visit weight should map back to the right name."""
    rng = random.Random(42)
    true_kg = {
        "Mochi": 3.2,
        "Bean": 3.9,
        "Luna": 4.6,
        "Shadow": 5.4,
        "Pumpkin": 6.8,
    }
    correct = 0
    total = 0
    for name, kg in true_kg.items():
        for _ in range(40):
            # Sensor noise ±120 g + occasional ±250 g wobble
            noise = rng.gauss(0, 80) + rng.choice([0, 0, 0, rng.uniform(-200, 200)])
            measured = _g(kg) + noise
            m = match_closest_pet(measured, FIVE_CATS)
            total += 1
            if m.pet_name == name:
                correct += 1
    accuracy = correct / total
    # With ~0.7–0.8 kg gaps, closest-weight should be very accurate
    assert accuracy >= 0.95, f"accuracy {accuracy:.2%} too low for 5-cat home"


def test_ambiguous_close_weights_still_picks_closest():
    """Two similar cats: still pick closest (app does), confidence may be low."""
    pets = [
        {"id": 1, "name": "TwinA", "weight": 4.50},
        {"id": 2, "name": "TwinB", "weight": 4.65},
    ]
    m = match_closest_pet(4520, pets)
    assert m.pet_name == "TwinA"
    assert m.confidence in ("high", "medium", "low")
    m2 = match_closest_pet(4620, pets)
    assert m2.pet_name == "TwinB"


def test_learned_weights_when_roster_lacks_weight():
    pets = [
        {"id": 1, "name": "Mochi"},
        {"id": 2, "name": "Bean"},
    ]
    learned = {"1": 4000.0, "2": 5500.0}
    m = match_closest_pet(4050, pets, learned)
    assert m.pet_name == "Mochi"


def test_stable_visit_weight_median_rejects_noise():
    # 200 too light; 15000 too heavy (person/lean); middle samples are the cat
    samples = [4200, 4250, 4300, 200, 15000]
    assert stable_visit_weight_g(samples) == pytest.approx(4250.0)


def test_implausible_weights_not_matched():
    assert not is_plausible_cat_weight(200)  # litter crumb
    assert not is_plausible_cat_weight(20000)  # person leaned on box
    m = match_closest_pet(200, FIVE_CATS)
    assert m.pet_name == "-"


def test_resolve_prefers_weight_over_wrong_api_name():
    """If device sends a wrong/stale name, weight should win for multi-cat."""
    props = {"petName": "Mochi"}  # wrong
    m = resolve_visit_identity(props, _g(6.7), FIVE_CATS)
    assert m.pet_name == "Pumpkin"
    assert m.method == "weight_closest"


def test_resolve_api_id_when_no_weight():
    props = {"petId": 3, "petName": "Luna"}
    m = resolve_visit_identity(props, None, FIVE_CATS)
    assert m.pet_name == "Luna"
    assert m.method in ("api_id", "api_name")


def test_multi_box_independent_visits():
    """Same roster; visits on different boxes get correct cats by weight."""
    # Box A: Luna; Box B: Shadow
    a = match_closest_pet(_g(4.55), FIVE_CATS)
    b = match_closest_pet(_g(5.35), FIVE_CATS)
    assert a.pet_name == "Luna"
    assert b.pet_name == "Shadow"


def test_update_learned_weight_ema():
    learned: dict[str, float] = {}
    update_learned_weight(learned, 1, "Mochi", 4000.0, alpha=0.5)
    update_learned_weight(learned, 1, "Mochi", 5000.0, alpha=0.5)
    assert learned["1"] == pytest.approx(4500.0)
