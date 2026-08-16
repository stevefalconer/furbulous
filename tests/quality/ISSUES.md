# Quality issues view (found → resolved)

Living log for UX/bugs discovered in review or field use. Keep permanent;
link tests that guard the fix.

| ID | Found | Status | Tier | Summary | Resolution | Guard test |
|----|-------|--------|------|---------|------------|------------|
| Q-001 | 1.3.4 feedback | **resolved** 1.3.5 | gold/uat | Duplicate Screen Off (legacy buttons + switch) | Orphan registry prune; only Screen off switch; diagnostic mirror disabled-by-default | `test_orphan_screen_buttons`, `test_screen_off_single_control` |
| Q-002 | 1.3.4 feedback | **resolved** 1.3.5 | gold | Settings mixed into Controls | Screen off, Full auto, Child lock, DND, cleaning delay → `EntityCategory.CONFIG` | `test_config_entity_categories` |
| Q-003 | 1.3.4 feedback | **resolved** 1.3.5 | uat | Empty + confirm not adjacent alphabetically | Rename confirm → **Empty confirm ready** | `test_empty_names_sort_together` |
| Q-004 | 1.3.4 feedback | **resolved** 1.3.5 | gold | 7d/30d averages not grouped | Prefix names `7d` / `30d` | `test_period_average_name_prefixes` |
| Q-005 | 1.3.4 feedback | **resolved** 1.3.5 | uat | PROBLEM sensors look odd with OK | Rename to *status*; attributes explain OK vs Problem | `test_problem_status_ok_semantics` |
| Q-006 | 1.3.4 feedback | **resolved** 1.3.5 | uat | Hand mode jargon | Rename **Box action** + cat-friendly labels | `test_box_action_labels` |
| Q-007 | 1.3.4 feedback | **resolved** 1.3.5 | gold | Eco start/stop times missing | Read-only Eco mode start/stop (+ DND times disabled-by-default) when API keys present; app-write until keys confirmed | `test_eco_mode_time_sensors` |
| Q-008 | 1.3.4 feedback | **resolved** 1.3.5 | uat | Activity lacks pet names | **Last visit activity** sensor `Name · time` | `test_last_visit_activity_includes_pet` |
| Q-009 | 1.3.4 feedback | **documented** 1.3.5 | gold | Many sensors show Unknown | Counts → 0; text → `-`; DURATION/WEIGHT/TIMESTAMP must use None (HA unknown) — documented | `test_empty_state_policy` |
| Q-010 | 1.3.4 feedback | **documented** 1.3.5 | gold | 11 sensors disabled | Expected: secondary analytics + day-over-day + DND times + screen mirror | `test_disabled_by_default_count` |
| Q-011 | 1.3.4 feedback | **documented** 1.3.5 | uat | Completion status meaning unclear | Renamed Cycle completion; best-effort map + raw attribute | `test_cycle_completion_mapping` |
| Q-012 | 1.3.4 feedback | **documented** 1.3.5 | uat | Full auto vs Pause/Resume | Documented on Full auto attributes + README | `test_full_auto_vs_pause_docs` |
| Q-013 | 1.3.6 UX review | **resolved** 1.3.6 | uat | Jargon names hard for non-tech cat parents | Plain-language renames (Last cat, Needs emptying, Clean now, …) | `test_cat_parent_primary_names_are_plain_english` |
| Q-014 | 1.3.6 UX review | **resolved** 1.3.6 | gold | Period metrics only used `7d`/`30d` codes | Word prefixes Visits/Bag/Litter + “N days” | `test_period_average_name_prefixes` |
| Q-015 | 1.3.6 UX review | **resolved** 1.3.6 | uat | Power users need event triggers without name scrape | Bus events visit/full/bag/litter/pack | `test_event_type_constants_are_namespaced`, `test_emit_event_fires_on_hass_bus` |
| Q-016 | 1.3.6 UX review | **resolved** 1.3.6 | uat | Adoption docs missing for non-tech vs power | CAT_PARENT_GUIDE + POWER_USER + UX_REVIEW | `test_adoption_docs_exist` |

## How to use

- **open** → bug still present  
- **documented** → intentional limitation or explained behavior  
- **resolved** → code shipped + guard test green  

When adding a new issue, pick the next `Q-NNN` id and add a failing test first when practical.
