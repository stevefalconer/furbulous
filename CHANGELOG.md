# Changelog

All notable changes to this fork are documented here.

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
