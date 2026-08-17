"""Shared box-state classifier (live 2026-08-16 API)."""
from __future__ import annotations

from custom_components.furbulous.box_state import (
    PHASE_CAT,
    PHASE_CLEANING,
    PHASE_IDLE,
    PHASE_RESETTING,
    PHASE_TRASH_DOOR,
    classify,
)
from custom_components.furbulous.helpers import is_cat_present


def test_idle_even_when_handmode_sticky():
    st = classify({"workstatus": 0, "handMode": 1, "completionStatus": 1})
    assert st.phase == PHASE_IDLE
    assert st.label == "Idle"
    assert st.cat_present is False


def test_clean_running_is_not_a_cat():
    st = classify({"workstatus": 1, "handMode": 1, "completionStatus": 3})
    assert st.phase == PHASE_CLEANING
    assert st.label == "Cleaning"
    assert st.cat_present is False
    assert is_cat_present({"workstatus": 1, "completionStatus": 2}) is False


def test_workstatus_1_without_completion_is_best_effort_cat():
    st = classify({"workstatus": 1, "completionStatus": 1})
    assert st.phase == PHASE_CAT
    assert st.cat_present is True
    assert st.label == "In use"


def test_e4_is_not_a_visit():
    st = classify(
        {
            "workstatus": 1,
            "completionStatus": 5,
            "errorReportEvent": 64 | 524288,
        }
    )
    assert st.phase == PHASE_TRASH_DOOR
    assert st.trash_door is True
    assert st.cat_present is False
    assert st.label == "Trash door jammed"


def test_litter_reset_workstatus():
    assert classify({"workstatus": 8}).phase == PHASE_RESETTING
    assert classify({"workstatus": 6}).label == "Resetting litter"


def test_handmode_fallback_when_workstatus_missing():
    st = classify({"handMode": 1})
    assert st.label == "Cleaning"
    assert st.cat_present is False


def test_waste_and_lid_flags():
    st = classify({"workstatus": 0, "errorReportEvent": 32 | 512})
    assert st.waste_full is True
    assert st.lid_off is True
    assert st.cat_present is False
