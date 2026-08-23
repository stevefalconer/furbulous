# Changelog

All notable changes to this fork are documented here.

## 1.4.2 — 2026-08-22

### Quality gate + persona review

- Gold UX test: bit **128** is No Bag (not cover); cover/lid is **512** — aligned with live `error_report` semantics.
- Persona review notes: `docs/reviews/2026-08-22-1.4.x-analytics-personas.md`.
- Bronze / silver / gold: **50 passed**.

## 1.4.1 — 2026-08-22

### Dashboard: compact Visits analytics row

- Each box stack: **status → status chips → Visits analytics → actions**.
- Visits card shows Today (± vs yesterday), 7d, 30d, on-bag, avg visit length, seals/30d — **omits unknown** segments; keeps `0` when that is real data.
- Same layout on Downstairs / Master / Cleo / Upstairs for consistency.

## 1.4.0 — 2026-08-22

### Analytics source hardening (first pass)

P0–P2 from the post-1.3.22 analytics review:

- **A1 (P0):** Barrel clean finish stamps **Last cleaned** even when the box was not Dirty/awaiting (Clean now, scheduled scoop, app clean). Dirty still clears only when awaiting was set.
- **A2 (P1):** `_cloud_event_ts` prefers the property that edged; optional skew rejects sticky ancient times on reconcile. Bag clear no longer falls back to sticky `handMode` time.
- **A3 (P2):** Device litter reset (`workstatus=8`) uses `property_times["workstatus"]`.
- **B1:** Live pack/seal (`workstatus` 3→0) records `pack` + **bag_replaced** (Seal = new bag), debounced with HA Seal button.
- **B2:** WC ingest skips append when a presence leave already covers the same sit (start/duration/weight window).

Unit tests cover A1–A3, B1, B2. Dashboard / UAT / quality-gate rounds follow on **1.4.x**.

## 1.3.22 — 2026-08-22

### API-first clocks (Last visit / cleaned / bag age)

- Preserve cloud property ``time`` stamps (`property_times`) instead of discarding them.
- Decode ``LocalTime`` as device **calendar date**; on day change reset WC ingest watermark (WC is today-only).
- Prefer `/device/data/wc` ``start_time`` for **Last visit** when the cloud returns rows.
- Prefer ``completionStatus`` / ``workstatus`` / ``errorReportEvent`` / ``handMode`` times for **Last cleaned** and **Bag age** when an edge is detected.
- ``timingShoveledShit`` documented as opaque (unused). API reference §5.0a–c and §10.5 state machine updated.

## 1.3.21 — 2026-08-22

### Stuck “cat / Dirty” while box is Idle

- Treat `workstatus=1` with no cat as a clean cycle so auto-clean is not missed between 30s polls.
- If awaiting-clean but the box is already healthy Idle/Complete and a clean cycle was seen, clear awaiting immediately (fixes Upstairs stuck on pet name / orange after the app already cleaned).
- `furbulous.mark_bag_replaced` accepts optional `hours_ago` to backdate Bag age (e.g. autopack earlier today).

## 1.3.20 — 2026-08-22

### Bag age + Last cleaned dashboard

- **Seal waste bag** now resets **Bag age** (same as Empty / full-clear / No Bag clear), so Seal → remove → new bag does not leave Bag age Unknown when the No Bag poll edge is missed.
- Service `furbulous.mark_bag_replaced` records a bag change in HA only (no cloud write).
- **Last cleaned** sensor shows **time/date only** (cat name remains in attributes).
- Dashboard: removed Instructions card; header stays last cat · visit time; Cleaned line uses time-only sensor.

## 1.3.19 — 2026-08-22

### Pause buttons vanish after Resume

- **Bug:** full-poll device prune treated the local **hub** device as a removed box, so Resume’s refresh deleted `switch.furbulous_pause_cloud_polling` (and the other pause entities). Pause/Pause 1 hr then never reappeared (Spook: unknown entity).
- Hub identifiers (`hub_<entry_id>`) are excluded from prune.
- Dashboard: Pause chips use `state_not: on` so they return whenever polling is not paused.

## 1.3.18 — 2026-08-22

### Stuck Dirty after missed auto-clean

- If a box is **Dirty** (≥30 min awaiting clean) but the cloud shows healthy **Idle** (no full / No Bag / E4), HA now records cleaned and clears the red toilet state (missed poll after bag-fix cleans).
- New **Mark cleaned** button + service `furbulous.mark_cleaned` (HA-only, no drum move).

## 1.3.17 — 2026-08-22

### No Bag + notifications + pause UX

- Live bag-replace capture: **No Bag = error bit 128**; lid off = **512**; cleared to **0** after new bag then clean ran.
- New **No Bag** PROBLEM binary; bag-status / error text updated.
- `mobile_notifications.yaml` = **automations** (not a dashboard) for bag full, No Bag, 15‑min reminder, E4, Dirty — Docker uses persistent notifications.
- Pause UI: show **Pause / Pause 1 hr** only while polling; **Resume** only while paused (conditional). Pause/resume driven by the switch so cycles repeat reliably.

## 1.3.16 — 2026-08-17

### Pause polling entity IDs + dashboard layout

- Normalize hub pause entities to stable IDs (`button.furbulous_pause_polling`, `sensor.furbulous_cloud_polling`, …) so dashboard chips are not unavailable.
- Dashboard: boxes **Downstairs → Master → Cleo → Upstairs**; pause controls **after** the boxes; status/action rows use equal 3-column widths (card-mod).

## 1.3.15 — 2026-08-17

### Dashboard + Dirty / Bag / Pause

- Dashboard: instructions at bottom; Pause Polling for Furbulous App Use; **Pause / Pause 1 hr / Resume** buttons; status **Polling (30s / 5min)** | **Paused** | **Paused until HH:MM**.
- Status row as markdown (Toilet | Bag | Errors); action chips directly below; **Refilled litter** label; cat icon red while Dirty.
- **Toilet / Dirty** clears on **auto-clean** (completion/workstatus edges), not only Clean now; dirty chip shows last cat name in red.
- **Bag status** sensor: Bag OK / Bag full / **No Bag** (live: No Bag ↔ Cover open bit when not full).
- **Bag age** resets on raw full→clear (`errorReportEvent` 16/32 → 0), not only the debounced is_full state.

## 1.3.14 — 2026-08-17

### Pause cloud polling (phone app / same account)

- Hub switch **Pause cloud polling** — stops 30s + 5min Furbulous API traffic until turned off.
- Button **Pause polling 1 hour** — same pause with automatic resume.
- Sensor **Cloud polling** status: Active / Paused / Paused until …
- Services `furbulous.pause_polling` / `furbulous.resume_polling`.
- Example dashboard header controls for pause + 1 hour.

## 1.3.13 — 2026-08-17

### Toilet status / Dirty after visit

- **Toilet status** sensor: `Idle` (green) · pet name while in use or &lt;30m waiting for a barrel clean (orange) · **Dirty** (red) at ≥30 minutes with no clean.
- **Needs cleaning** PROBLEM binary + event `furbulous_needs_cleaning` for Companion alerts.
- **Last cleaned** sensor: `Paulie · 21:57 8-17` (cat from the visit before the clean).
- Barrel clean detection via live cleaning phase / completionStatus finish (and Clean now arming).

### Dashboard

- Combined header: cat · visit time (no Idle on that line; no name repeat).
- Toilet chip uses Toilet status colors; error chip **No errors** / **Litter door error** (not “Door OK”).
- Shows **Last cleaned** on the status line.

## 1.3.12 — 2026-08-17

### Dashboard / Last visit

- **Last visit** is a compact local stamp (`21:57 8-17`) — no year, no cat name (name stays on **Last cat** so phone cards do not truncate).
- Example Mushroom dashboard adds **Cleo**, separates **Status** (green/red) from **Actions** (Clean now / Seal bag / Refilled), and shows Litter/Bag age as hours or days without glance truncation.
- Example Companion notification automations: `docs/dashboards/mobile_notifications.yaml`.

### Bag age

- When a confirmed **bag-full** condition clears in the cloud (`Needs emptying` → OK), analytics records **`bag_replaced`** so **Bag age** restarts after you remove the sealed bag / clear the full error (Seal alone still does not).

### Docs

- Dedicated Furbulous account for HA; pets shared from other accounts are **not verified**.
- Clean = barrel cycle; Seal vs emptied bag vs Bag age clarified; Litter age **Unknown** until **I refilled**.

### Known follow-ups

- Master **Screen mode Scheduled**: overnight blank verified; mid-day unexpected off noted for later eco/schedule troubleshooting.
- Shared-account pets: investigate later.

## 1.3.11 — 2026-08-16

### One box-state classifier

- Occupancy, **What the box is doing**, and visit edges share `box_state.classify()`.
- 5-minute full poll no longer opens visits (presence owns those edges so a stale snapshot cannot invent a cat).
- Visit / bag / litter events flush to disk immediately instead of waiting up to 60s.
- New **Trash door jammed** PROBLEM sensor (E4 / bit 524288). Attributes and the cat-parent guide say the usual cause (clump on the waste door) and the fix (scoop, then **OK on the box**). Example Mushroom dashboard (`docs/dashboards/`) — edit entity ID prefixes for your areas/box names.

## 1.3.10 — 2026-08-16

### Cat inside vs clean

- **Cat inside** and visit analytics ignore a **running clean** (`completionStatus=3`) and a **trash-door E4** (`524288`). Those used the same `workstatus=1` as a cat.

### Litter reset (physical)

- **I refilled the litter** now sends **`handMode=6`** (spread + tare, same as the on-box menu) and still records Litter age.

### Auth / docs

- Login token is reused for the HA session; re-login only on real auth/token errors (not every message that says “expired”).
- Docs: dedicated Furbulous account (app looks single-session), bitwise `errorReportEvent`, display apply lag, timezone retrospective (UTC-only does not explain all three boxes).

### Errors (live 2026-08-16)

- **Needs emptying** treats **16 and 32** as full (Upstairs live full was **32**, not 16).
- **Cover / lid off** is bit **512** (lid removed). Documented **128** still counts if it appears.
- **Trash door blocked** is bit **524288** (with 64) — screen **Device Failure E4**. Not “drawer.”
- **Drawer out of place** no longer uses bit 64 (physical drawer-out stayed `0` on the cloud).
- Error text walks bits above 512 so E4 is not invisible.

### Screen / Eco (live Downstairs)

- **Always on** (`DisplaySwitch=0`) stays lit overnight.
- **Scheduled / Eco** (`DisplaySwitch=1`) blanks **inside** start–end; minutes are **house-local** (PDT). Virginia/UTC windows did not match.
- **Screen is off** is schedule intent, not live pixels. A button always wakes a dark Eco panel.
- Cloud child lock on/off matches the locked screen / menu.

### Cleanup after 1.3.9 review

- Removed unused **Screen off** switch class (`masterSleepOnOff` is not the panel control).
- Child lock / mode / delay / schedule / Clean now writes update the local snapshot immediately so the HA UI does not wait on a stale cloud GET.
- **What the box is doing** and **Clean cycle status** now follow the 30-second properties poll.
- **Screen mode** options are translation keys (`always_on` / `scheduled`) in all language packs.
- API + cat-parent docs aligned with DisplaySwitch / Screen mode (no longer describe the old Screen off switch as current).

## 1.3.9 — 2026-08-16

### Display (physically verified API model)

- **Screen mode** select: **Always on** (`DisplaySwitch=0`) or **Scheduled** (`DisplaySwitch=1`).
- **Screen schedule start/end** write `displayStartTime` / `displayEndTime` (minutes).
- Removed misleading **Screen off** switch (`masterSleepOnOff` alone does not drive the panel).
- **Screen blank now** binary uses DisplaySwitch + schedule window.

### Quiet hours / pets / activity

- Quiet hours start/end map to **`sleepTimeStart` / `sleepTimeStop`**.
- Pet roster: `unit=1` → **pounds**; normalize `nickname` / `pet_id`.
- Ingest **`/device/data/wc`** visit history for Last cat (when the API returns rows for the current day).

### Docs

- [`docs/api/FURBULOUS_API_REFERENCE.md`](docs/api/FURBULOUS_API_REFERENCE.md) — empirical API + physical checks.

## 1.3.8 — 2026-08-16

### Screen off / Quiet hours schedules (writable)

- **Screen off start** / **Screen off end** and **Quiet hours start** / **Quiet hours end** are enabled **time** entities under Configuration.
- Writes go to the cloud via `properties/set` (format matches device: minutes, HHMM, or `HH:MM`).
- Names align with the enable switches so they sort together (Screen off… / Quiet hours…).
- Device applies Screen off / Quiet hours only inside the daily window — set both times.

### Naming & enablement

- **Auto-clean minutes before** (was “Minutes before auto-clean”) sorts next to **Auto-clean after visits**.
- **Screen is off** diagnostic enabled.
- All previously default-disabled sensors enabled; one-shot registry enable for existing installs.

## 1.3.7 — 2026-08-16

### Breaking (pre–public adoption): cat-parent entity unique_ids

- All litter-box unique_ids rewritten to  
  `furbulous_{device_id}_{slug}` with **cat-language slugs**  
  (e.g. `last_cat`, `needs_emptying`, `empty_waste`, `bag_age_hours`,  
  `auto_clean_after_visits`, `what_box_doing`).
- Pets: `furbulous_pet_{id}_{slug}`.
- One-shot registry **purge** on upgrade recreates entities so no orphan  
  “unavailable” leftovers from old camelCase / iotid-prefix IDs.
- Central map: `custom_components/furbulous/entity_ids.py`.

Safe because this fork is not yet widely adopted and has no production automations.

## 1.3.6 — 2026-08-16

### Cat-parent usability (names) without removing power features

- **Plain-language entity names** for non-technical multi-cat homes, e.g. **Last cat**, **Last visit**, **Who is inside**, **Needs emptying**, **Clean now**, **Empty waste**, **Empty — confirm ready**, **Seal waste bag**, **I refilled the litter**, **Auto-clean after visits**, **Quiet hours**, **Bag age**, **Litter age**, **Visits (7/30 days)**.
- **unique_ids unchanged** — automations keep working when labels improve.
- **Power-user bus events:** `furbulous_visit_ended`, `furbulous_waste_full`, `furbulous_waste_cleared`, `furbulous_bag_replaced`, `furbulous_pack`, `furbulous_litter_reset`.
- Attributes: `audience`, `automation_hint`, `vendor_property`, `metric_key`, raw codes.
- Adoption docs: [docs/CAT_PARENT_GUIDE.md](docs/CAT_PARENT_GUIDE.md), [docs/POWER_USER.md](docs/POWER_USER.md), [docs/UX_REVIEW_1.3.6.md](docs/UX_REVIEW_1.3.6.md).
- Quality UAT for naming + events + doc presence (`tests/quality/uat/`).

## 1.3.5 — 2026-08-16

### Controls / Configuration UX (user feedback)

- **Single Screen off control:** ON = display blank/dim; OFF = screen normal. Legacy Screen on/off **buttons** are pruned from the entity registry on setup.
- **Configuration section:** Screen off, Full auto mode, Do not disturb, Child lock, Cleaning delay, Eco mode start/stop.
- **Controls section:** Empty, **Empty confirm ready** (renamed so it sorts next to Empty), Manual clean, Pause/Resume, Pack, Mark litter reset.
- **Eco mode start / stop** sensors (read when API returns schedule properties; write remains in the app until keys are confirmed).
- Diagnostic **Screen off active** mirror disabled by default (avoids looking like a second Screen off).

### Naming & sensors

- Problem binaries → **Waste bin status**, **Cover status**, **Drawer status** (HA **OK** / **Problem**).
- **Hand mode** → **Box action** (Idle / Cleaning / Emptying / Packing bag / Paused / Resuming).
- **Completion status** → **Cycle completion** with best-effort labels + raw attribute.
- Period metrics prefixed **7d** / **30d** for alphabetical grouping.
- **Last visit activity** sensor: `PetName · time` for Activity/Logbook.
- Counts default to **0**; text empties **`-`**; WEIGHT/DURATION/TIMESTAMP still use HA **unknown** when empty (documented).

### Quality suite

- Persistent `tests/quality/{bronze,silver,gold,performance,uat}/` with [PROMPTS.md](tests/quality/PROMPTS.md) and [ISSUES.md](tests/quality/ISSUES.md).

## 1.3.4 — 2026-08-16

### Multi-cat identity (5 cats × many boxes)

- **App-style matching:** after each visit, pick the roster cat with the **smallest weight delta** vs measured `catWeight` (weight-first over stale property names).
- Uses `pet/list` profile weights when present; otherwise **learns** weights from past visits (EMA).
- **Median of samples** during the visit resists litter/sensor noise; rejects implausible weights.
- Confidence + delta on **Last visitor** attributes; carry identity if exit poll drops `petName`.
- Realistic tests: 5 cats with ±noise, 3 boxes end-to-end, ambiguous twins.

### UX (also since 1.3.2)

- **Controls** (not Configuration): delay, child lock, screen off, confirm empty.
- **Empty safety:** **Confirm empty ready** (90s) then **Empty**.
- Text empty states **`-`**; **Screen off** toggle (replaces separate screen buttons).
- Pet roster **≤1 min**; properties **30s**; list/stats **5 min**.

## 1.3.1 — 2026-08-16

### Features

- **Last visit snapshot** (better fit for 30s polls vs short visits):
  - **Last visitor**, **Last visit time**, **Last visit weight**
- **Energy saving** switch (`masterSleepOnOff`) + diagnostic **Energy saving active**.
- **Do not disturb** attributes clarify schedule times are managed in the app.

### Notes

- DND and energy-saving **schedule windows** are not reverse-engineered; HA toggles active state only.

## 1.3.0 — 2026-08-16

### Fixes (gap closure + verification)

- **Weight UI:** Detect real HA `US_CUSTOMARY_SYSTEM` / metric (`mass_unit` is often **g** on metric) and always expose **lb** or **kg** — never grams. Verified under real HA unit systems in `tests/test_weight_ha.py`.
- **Translations:** New entity keys merged into all language packs.
- **Visit identity:** Keep pet name across exit polls when properties drop identity fields.
- Expanded unit + full HA harness tests for analytics (pack/empty/litter/visits/pets/diagnostics).

### Features — cat-lover analytics & API visibility

- **Local analytics engine** (Layer B): append-only event store (90-day retention, Pi-safe cap), occupancy/full edge detection on the 30s presence path, Empty/Pack/litter-reset command hooks.
- **Chore metrics per box:** bag lifetime (last/avg/30d count/current age), time-to-clear full bag (live wait, last, avg, max), litter reset intervals (helper button **Mark litter reset**), pack frequency + visits since pack.
- **Visit metrics:** visits 7d/30d, avg duration 30d, occupying pet / last visitor (Unknown when unidentified).
- **Pet roster:** `pet/list` on full poll only; HA pet devices with visits, avg duration, favorite box, last seen.
- **P0b live API surface** (no extra HTTP): firmware, hand mode, completion status, uses/duration vs yesterday, cover open, drawer not in place.
- Weight remains **calculated lb/kg** from HA unit system (1.2.2).

### Performance

- Pets + daily stats only on **5 min** full poll; presence path still properties-only.
- Analytics idle path: **no full history recompute** on quiet 30s ticks; live full-wait is O(devices).
- Per-device event index; 90-day prune + 50k cap; **debounced disk flush** (60s) + force flush on unload.
- State-write fingerprints on coordinator and analytics entities (skip unchanged).
- Secondary sensors **disabled by default** (hours-since, 7d, max clear, day-over-day, …).
- Quality scale re-reviewed Bronze/Silver/Gold lean for 1.3.0 (`quality_scale.md`).

## 1.2.2 — 2026-08-16

### Fixed

- **Cat weight always follows HA unit system by calculation:** API grams are converted in the integration to **lb** (US Customary) or **kg** (metric) as the sensor’s `native_value` / `native_unit_of_measurement`. No longer depends on sticky entity-registry unit conversion or `suggested_unit_of_measurement` (which left many US installs stuck on `g`). One-shot registry clear on upgrade to 1.2.2 removes leftover unit locks.

## 1.2.1 — 2026-08-16

### Fixed

- **Cat weight in pounds:** Home Assistant does not auto-convert weight `g`→`lb` from the unit system (unlike temperature). The weight sensor now **suggests** `hass.config.units.mass_unit` (lb under US Customary). Reconfigure/reauth and the upgrade path force a registry refresh of that suggested unit so existing installs pick up lb without a manual entity edit (manual entity unit → lb still works anytime). *(Superseded by 1.2.2 calculated units.)*

## 1.2.0 — 2026-08-15

### Breaking / behavior

- **Region is required** at setup (US Supported; EU and Asia Experimental).
- Existing 1.1.x config entries migrate automatically: `region=us`, unique id becomes `email_region`.
- Cat weight remains **native grams** with `SensorDeviceClass.WEIGHT` so Home Assistant converts to lb/kg. If the UI still shows `g`, set the entity unit to lb/kg once (entity registry stickiness).
- **Minimum Home Assistant:** 2024.4.0 (uses `ConfigEntry.runtime_data`).

### Features

- Multi-region cloud login (`us` / `eu` / `asia`) with clear Supported vs Experimental labels.
- Async **aiohttp** API client using HA’s shared session (`async_get_clientsession`).
- Split polling: **5 min** full snapshot; **30 s** presence-only for cat-in-box (no full poll every 30 s).
- **Dynamic devices:** new litter boxes appear as entities without reloading the integration.
- **Reconfigure / reauth** clear sticky entity-registry unit and name overrides so weight follows HA unit system (lb/kg from native grams) and labels follow HA language packs—not leftover g/kg/lb or old hardcoded names.
- One-shot on first 1.2.0 load: clear weight unit locks from 1.1.x upgrades (preserves intentional custom names).
- HA entity naming: `has_entity_name` + `translation_key`.
- Language packs: en, fr, de, es, it, pt-BR, ja, ko, zh-Hans, zh-Hant, ru (starting points).
- Reauth and **reconfigure** flows (email / password / region).
- Diagnostics platform with redacted secrets.
- Icon translations (`icons.json`).
- Entity categories (diagnostic / config) for secondary entities.
- Stale device pruning when a litter box disappears from the cloud account.
- Action failures raise `HomeAssistantError` with translated messages.

### Performance / reliability

- One API client per config entry; entities never poll the cloud.
- State writes skipped when entity fingerprints are unchanged.
- Logging: once when unavailable / restored; DEBUG for timings; no password/token logs.
- Pets endpoint no longer polled (no entities used it).

### Docs / packaging / tests

- README: full user/reviewer sections (how it works, regions, recovery, diagnostics, support policy).
- GitHub issue templates (bug + config failure); `quality_scale.md` checklist.
- HACS `homeassistant` requirement raised to 2024.4.0.
- `CODEOWNERS` added.
- Unit tests (API, regions, weight, dynamic devices, coordinator, entity smoke) + full HA harness tests (config flow, setup/unload) via `pytest-homeassistant-custom-component`.

## 1.1.2

- English entity cleanup; weight/duration device classes; neutral packaging.

## 1.1.1

- US cloud default; English UI.
