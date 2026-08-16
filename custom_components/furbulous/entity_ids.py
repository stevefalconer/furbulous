"""Cat-parent entity unique_id scheme (v1, pre–public adoption).

Format for litter-box entities::

    furbulous_{device_id}_{slug}

Format for pet entities::

    furbulous_pet_{pet_key}_{slug}

Slugs match how cat parents talk about the feature (not vendor camelCase).
Entity *display* names come from translations; unique_ids stay in English snake_case
so entity_ids in HA remain readable (e.g. ``sensor.box_last_cat``).

Breaking: rewritten in 1.3.7. A one-shot registry purge recreates entities cleanly.
"""
from __future__ import annotations


def box_uid(device_id: int | str, slug: str) -> str:
    """Stable unique_id for a litter-box entity."""
    return f"furbulous_{device_id}_{slug}"


def pet_uid(pet_key: str, slug: str) -> str:
    """Stable unique_id for a pet roster entity."""
    return f"furbulous_pet_{pet_key}_{slug}"


# --- Box slugs (aligned with friendly names) ---
UID_DEVICE_LAST_ACTIVE = "device_last_active"
UID_CAT_WEIGHT = "cat_weight"
UID_USES_TODAY = "uses_today"
UID_AVERAGE_VISIT_TODAY = "average_visit_today"
UID_ERROR_MESSAGE = "error_message"
UID_FIRMWARE = "firmware"
UID_WHAT_BOX_DOING = "what_box_doing"
UID_CLEAN_CYCLE_STATUS = "clean_cycle_status"
UID_USES_VS_YESTERDAY = "uses_vs_yesterday"
UID_VISIT_LENGTH_VS_YESTERDAY = "visit_length_vs_yesterday"
UID_SCREEN_OFF_SCHEDULE_START = "screen_off_schedule_start"
UID_SCREEN_OFF_SCHEDULE_END = "screen_off_schedule_end"
UID_QUIET_HOURS_START = "quiet_hours_start"
UID_QUIET_HOURS_END = "quiet_hours_end"

UID_ONLINE = "online"
UID_CAT_INSIDE = "cat_inside"
UID_NEEDS_EMPTYING = "needs_emptying"
UID_COVER_OPEN = "cover_open"
UID_DRAWER_OUT_OF_PLACE = "drawer_out_of_place"
UID_CHILD_LOCK_ON = "child_lock_on"
UID_SCREEN_IS_OFF = "screen_is_off"

UID_AUTO_CLEAN_AFTER_VISITS = "auto_clean_after_visits"
UID_QUIET_HOURS = "quiet_hours"
UID_SCREEN_OFF = "screen_off"
UID_CHILD_LOCK = "child_lock"
UID_EMPTY_CONFIRM_READY = "empty_confirm_ready"

UID_CLEAN_NOW = "clean_now"
UID_PAUSE_CLEANING = "pause_cleaning"
UID_RESUME_CLEANING = "resume_cleaning"
UID_EMPTY_WASTE = "empty_waste"
UID_SEAL_WASTE_BAG = "seal_waste_bag"
UID_LITTER_REFILLED = "litter_refilled"
UID_MINUTES_BEFORE_AUTO_CLEAN = "minutes_before_auto_clean"

UID_WHO_IS_INSIDE = "who_is_inside"
UID_LAST_CAT = "last_cat"
UID_LAST_VISIT = "last_visit"
UID_LAST_VISIT_TIME = "last_visit_time"
UID_LAST_VISIT_WEIGHT = "last_visit_weight"

UID_VISITS_7_DAYS = "visits_7_days"
UID_VISITS_30_DAYS = "visits_30_days"
UID_VISIT_LENGTH_AVG_30_DAYS = "visit_length_average_30_days"
UID_WAITING_WITH_FULL_BAG = "waiting_with_full_bag"
UID_LAST_WAIT_UNTIL_EMPTIED = "last_wait_until_emptied"
UID_AVG_WAIT_UNTIL_EMPTIED_30_DAYS = "average_wait_until_emptied_30_days"
UID_LONGEST_WAIT_UNTIL_EMPTIED_30_DAYS = "longest_wait_until_emptied_30_days"
UID_TIMES_BAG_FILLED_30_DAYS = "times_bag_filled_30_days"
UID_LAST_BAG_SEAL = "last_bag_seal"
UID_HOURS_SINCE_BAG_SEAL = "hours_since_bag_seal"
UID_AVG_HOURS_BETWEEN_SEALS_30_DAYS = "average_hours_between_seals_30_days"
UID_BAG_SEALS_30_DAYS = "bag_seals_30_days"
UID_VISITS_SINCE_BAG_SEAL = "visits_since_bag_seal"
UID_BAG_LAST_CHANGED = "bag_last_changed"
UID_BAG_AGE_HOURS = "bag_age_hours"
UID_BAG_LAST_LIFESPAN = "bag_last_lifespan"
UID_BAG_AVERAGE_LIFE_30_DAYS = "bag_average_life_30_days"
UID_BAGS_USED_30_DAYS = "bags_used_30_days"
UID_VISITS_ON_LAST_BAG = "visits_on_last_bag"
UID_LITTER_LAST_REFILLED = "litter_last_refilled"
UID_LITTER_AGE_HOURS = "litter_age_hours"
UID_LITTER_LAST_INTERVAL = "litter_last_interval"
UID_LITTER_AVERAGE_INTERVAL_30_DAYS = "litter_average_interval_30_days"
UID_LITTER_REFILLS_30_DAYS = "litter_refills_30_days"

# Pet roster
UID_PET_VISITS_7_DAYS = "visits_7_days"
UID_PET_VISITS_30_DAYS = "visits_30_days"
UID_PET_VISIT_LENGTH_AVG_30_DAYS = "visit_length_average_30_days"
UID_PET_FAVORITE_BOX = "favorite_litter_box"
UID_PET_LAST_SEEN = "last_seen"
