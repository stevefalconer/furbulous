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
| Q-008 | 1.3.4 feedback | **resolved** 1.3.12 | uat | Last visit truncation on phones | Compact `H:MM M-D`; cat on **Last cat** + attr | `test_last_visit_activity_is_compact_time` |
| Q-009 | 1.3.4 feedback | **documented** 1.3.5 | gold | Many sensors show Unknown | Counts → 0; text → `-`; DURATION/WEIGHT/TIMESTAMP must use None (HA unknown) — documented | `test_empty_state_policy` |
| Q-010 | 1.3.4 feedback | **documented** 1.3.5 | gold | 11 sensors disabled | Expected: secondary analytics + day-over-day + DND times + screen mirror | `test_disabled_by_default_count` |
| Q-011 | 1.3.4 feedback | **documented** 1.3.5 | uat | Completion status meaning unclear | Renamed Cycle completion; best-effort map + raw attribute | `test_cycle_completion_mapping` |
| Q-012 | 1.3.4 feedback | **documented** 1.3.5 | uat | Full auto vs Pause/Resume | Documented on Full auto attributes + README | `test_full_auto_vs_pause_docs` |
| Q-013 | 1.3.6 UX review | **resolved** 1.3.6 | uat | Jargon names hard for non-tech cat parents | Plain-language renames (Last cat, Needs emptying, Clean now, …) | `test_cat_parent_primary_names_are_plain_english` |
| Q-014 | 1.3.6 UX review | **resolved** 1.3.6 | gold | Period metrics only used `7d`/`30d` codes | Word prefixes Visits/Bag/Litter + “N days” | `test_period_average_name_prefixes` |
| Q-015 | 1.3.6 UX review | **resolved** 1.3.6 | uat | Power users need event triggers without name scrape | Bus events visit/full/bag/litter/pack | `test_event_type_constants_are_namespaced`, `test_emit_event_fires_on_hass_bus` |
| Q-016 | 1.3.6 UX review | **resolved** 1.3.6 | uat | Adoption docs missing for non-tech vs power | CAT_PARENT_GUIDE + POWER_USER + UX_REVIEW | `test_adoption_docs_exist` |
| Q-017 | 1.3.7 | **resolved** 1.3.7 | bronze | unique_ids still vendor camelCase / iotid | Cat-parent slug scheme + one-shot purge | `test_all_box_unique_ids_use_cat_parent_scheme` |
| Q-018 | 1.3.8 | **resolved** 1.3.8 | gold | Screen/Quiet schedules read-only / wrong names | Writable time entities named Screen off / Quiet hours start|end | `test_screen_off_and_quiet_hours_time_entities_writable` |
| Q-019 | 1.3.8 | **resolved** 1.3.8 | gold | Secondary sensors + Screen is off disabled | All enabled by default + one-shot registry enable | `test_all_entities_enabled_by_default` |
| Q-020 | 1.3.9 review | **resolved** 1.3.10 | silver | Dead `FurbulousEnergySavingSwitch` left in switch.py | Deleted unused class | `test_energy_saving_switch_removed` |
| Q-021 | 1.3.9 review | **resolved** 1.3.10 | silver | Child lock HA UI lagged until later refresh | Optimistic local snapshot after write; skip immediate stale GET | `test_child_lock_write_updates_local_snapshot` |
| Q-022 | 1.3.9 review | **resolved** 1.3.10 | gold | What the box is doing lagged on 5 min coordinator | Bind box action + cycle status to 30s presence | `test_box_action_and_cycle_status_use_presence_coordinator` |
| Q-023 | 1.3.9 review | **resolved** 1.3.10 | gold/uat | Screen mode options English-only | Translation keys + all language packs | `test_screen_mode_options_are_translation_keys`, `test_all_language_packs_translate_screen_mode_options` |
| Q-024 | 2026-08-16 field | **resolved** 1.3.10 | gold | Upstairs full but Needs emptying OK (`errorReportEvent=32`) | Treat 16 and 32 as full; bit masks for cover/drawer | `test_waste_full_accepts_16_and_32`, `test_needs_emptying_entity_on_for_upstairs_code_32` |
| Q-025 | 2026-08-16 field | **resolved** 1.3.10 | gold | Error bits 64/128/512/524288 mislabeled | 512=lid; 524288=E4 trash door; drawer not a cloud bit; describe_error walks high bits | `test_cover_is_lid_off_or_documented_128`, `test_trash_door_e4`, `test_problem_status_ok_semantics` |
| Q-026 | 2026-08-16 field | **documented** 1.3.10 | gold | Screen blank now ≠ physical panel | Eco blanks inside local window; entity is schedule intent; button wakes | CAT_PARENT + API §5.8 |
| Q-027 | 1.3.10 review | **resolved** 1.3.11 | gold | Dual coordinator + scattered workstatus ifs invented visits | `box_state.classify`; presence-only edges; trash-door entity; immediate flush | `test_box_state.py`, `test_full_recompute_does_not_open_a_visit` |
| Q-028 | 2026-08-17 field | **resolved** 1.3.12 | uat | Clean/Seal/Bag age confusion; Litter Unknown after pour | Docs + dashboard Status vs Actions; bag age on full-clear | CAT_PARENT + dashboard README |
| Q-029 | 2026-08-17 field | **open** | gold | Master Scheduled screen off mid-day unexpectedly | Overnight OK; mid-day blank noted — eco/schedule follow-up | — |
| Q-030 | 2026-08-17 field | **documented** | uat | Pets shared from another Furbulous account | Not verified; recommend all pets on HA account | CAT_PARENT |

## How to use

- **open** → bug still present  
- **documented** → intentional limitation or explained behavior  
- **resolved** → code shipped + guard test green  

When adding a new issue, pick the next `Q-NNN` id and add a failing test first when practical.
| Q-031 | 2026-08-22 field | **resolved** 1.4.3 | uat | Dashboard collapsed to one action row / one Visits block | Rebuild per-box stacks + House totals | Playwright layout check (manual) |
| Q-032 | 2026-08-22 field | **resolved** 1.4.4 | uat | Today metrics truncated; Pause chips not in own section; status chips above metrics | Per-box order cat→Today/7d→chores→status→actions; Pause own stack; multi-card metrics | Playwright mobile check |
