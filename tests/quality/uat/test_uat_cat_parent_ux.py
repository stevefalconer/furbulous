"""UAT: cat-parent naming + power-user contracts (1.3.6)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.furbulous.events import (
    EVENT_BAG_REPLACED,
    EVENT_LITTER_RESET,
    EVENT_PACK,
    EVENT_VISIT_ENDED,
    EVENT_WASTE_CLEARED,
    EVENT_WASTE_FULL,
    emit_event,
)
from custom_components.furbulous.ux import ROLE_PRIMARY, power_attrs


def _strings():
    return json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "custom_components"
            / "furbulous"
            / "strings.json"
        ).read_text()
    )


def test_cat_parent_primary_names_are_plain_english():
    s = _strings()["entity"]
    assert s["sensor"]["last_visitor"]["name"] == "Last cat"
    assert s["sensor"]["last_visit_activity"]["name"] == "Last visit"
    assert s["sensor"]["occupying_pet"]["name"] == "Who is inside"
    assert s["binary_sensor"]["cat_in_litter_box"]["name"] == "Cat inside"
    assert s["binary_sensor"]["waste_bin_status"]["name"] == "Needs emptying"
    assert s["switch"]["full_auto_mode"]["name"] == "Auto-clean after visits"
    assert s["switch"]["do_not_disturb"]["name"] == "Quiet hours"
    assert s["button"]["manual_clean"]["name"] == "Clean now"
    assert s["button"]["empty"]["name"] == "Empty waste"
    assert s["button"]["pack"]["name"] == "Seal waste bag"
    assert s["button"]["mark_litter_reset"]["name"] == "I refilled the litter"
    assert s["switch"]["empty_confirm_ready"]["name"].startswith("Empty")
    assert s["select"]["cleaning_delay"]["name"].startswith("Auto-clean")
    assert s["time"]["screen_off_start"]["name"].startswith("Screen off")
    assert s["time"]["screen_off_end"]["name"].startswith("Screen off")
    assert s["time"]["quiet_hours_start"]["name"].startswith("Quiet hours")
    assert s["time"]["quiet_hours_end"]["name"].startswith("Quiet hours")


def test_chore_names_group_for_scanning():
    s = _strings()["entity"]["sensor"]
    assert s["hours_since_bag_replaced"]["name"].startswith("Bag")
    assert s["last_bag_replaced"]["name"].startswith("Bag")
    assert s["avg_bag_lifetime_30d"]["name"].startswith("Bag")
    assert s["hours_since_litter_reset"]["name"].startswith("Litter")
    assert s["last_litter_reset"]["name"].startswith("Litter")
    assert s["visits_7_days"]["name"].startswith("Visits")
    assert s["visits_30_days"]["name"].startswith("Visits")


def test_empty_pair_still_sorts_together():
    s = _strings()["entity"]
    empty = s["button"]["empty"]["name"]
    confirm = s["switch"]["empty_confirm_ready"]["name"]
    assert empty.startswith("Empty")
    assert confirm.startswith("Empty")


def test_power_attrs_preserve_automation_hooks():
    attrs = power_attrs(
        role=ROLE_PRIMARY,
        automation_hint="use event",
        vendor_property="handMode",
        metric_key="visits_30d",
        raw=1,
    )
    assert attrs["audience"] == ROLE_PRIMARY
    assert attrs["vendor_property"] == "handMode"
    assert attrs["metric_key"] == "visits_30d"
    assert attrs["raw_value"] == 1
    assert "automation_hint" in attrs


def test_event_type_constants_are_namespaced():
    assert EVENT_VISIT_ENDED.startswith("furbulous_")
    assert EVENT_WASTE_FULL.startswith("furbulous_")
    assert EVENT_WASTE_CLEARED.startswith("furbulous_")
    assert EVENT_BAG_REPLACED.startswith("furbulous_")
    assert EVENT_LITTER_RESET.startswith("furbulous_")
    assert EVENT_PACK.startswith("furbulous_")


def test_emit_event_fires_on_hass_bus():
    hass = MagicMock()
    emit_event(hass, EVENT_VISIT_ENDED, {"pet_name": "Luna", "device_id": "1"})
    hass.bus.async_fire.assert_called_once()
    args = hass.bus.async_fire.call_args[0]
    assert args[0] == EVENT_VISIT_ENDED
    assert args[1]["pet_name"] == "Luna"
    assert args[1]["domain"] == "furbulous"


def test_emit_event_noop_without_hass():
    emit_event(None, EVENT_VISIT_ENDED, {"pet_name": "x"})  # must not raise


def test_adoption_docs_exist():
    root = Path(__file__).resolve().parents[3]
    for rel in (
        "docs/CAT_PARENT_GUIDE.md",
        "docs/POWER_USER.md",
        "docs/UX_REVIEW_1.3.6.md",
        "tests/quality/PROMPTS.md",
        "tests/quality/ISSUES.md",
    ):
        path = root / rel
        assert path.is_file(), rel
        text = path.read_text()
        assert len(text) > 200
