# Integration quality scale checklist (HACS custom)

Tracking against [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/).  
Status: **PASS** | **EXEMPT** (with reason). Not a core submission claim.

**Last reviewed:** 2026-08-16 (**v1.3.5**)

Automated tests:

```bash
.venv/bin/pytest tests/ -q
.venv/bin/pytest tests/quality/ -q   # bronze / silver / gold / performance / UAT
```

Repeatable prompts: [tests/quality/PROMPTS.md](tests/quality/PROMPTS.md) · Issue log: [tests/quality/ISSUES.md](tests/quality/ISSUES.md)

---

## Bronze

| Rule | Status | Notes |
|------|--------|--------|
| config-flow | PASS | UI setup; data_description |
| test-before-configure | PASS | Auth + device list before create_entry |
| test-before-setup | PASS | ConfigEntryAuthFailed / ConfigEntryNotReady |
| unique-config-entry | PASS | unique_id email_region |
| entity-unique-id | PASS | Stable box + pet + analytics ids |
| has-entity-name | PASS | Base + analytics entities |
| runtime-data | PASS | api, dual coordinators, analytics |
| appropriate-polling | PASS | 30s properties; pets ≤1 min; 5 min list/stats |
| common-modules | PASS | api, coordinator, analytics, pet_match, schedule_props |
| docs-high-level / install / removal | PASS | README current for 1.3.5 |

---

## Silver

| Rule | Status | Notes |
|------|--------|--------|
| config-entry-unloading | PASS | Flush analytics; cancel flush tasks |
| reauthentication-flow | PASS | reauth |
| entity-unavailable | PASS | last_update_success |
| log-when-unavailable | PASS | Once down / once up |
| parallel-updates | PASS | PARALLEL_UPDATES = 0 |
| integration-owner | PASS | CODEOWNERS + manifest |
| action-exceptions | PASS | HomeAssistantError + empty_not_confirmed |

---

## Gold (lean)

| Rule | Status | Notes |
|------|--------|--------|
| devices | PASS | Box + pet devices |
| entity-device-class | PASS | weight, duration, connectivity, problem |
| entity-translations | PASS | strings + locale packs |
| exception-translations | PASS | exceptions in strings |
| entity-category | PASS | CONFIG settings; Controls for Empty chore; diagnostic support |
| diagnostics | PASS | Redacted + analytics counts |
| docs-known-limitations | PASS | Eco/DND schedule write in app; multi-cat weight gaps |
| docs-data-update | PASS | Dual poll + pet throttle |
| docs-supported-functions | PASS | README entities + empty safety + multi-cat + OK status |
| reconfiguration-flow | PASS | reconfigure |
| stale-devices | PASS | Boxes + pets pruned |
| entity-disabled-by-default | PASS | Secondary analytics + DND times + screen mirror off by default |
| discovery | EXEMPT | Cloud login only |

---

## Performance (1.3.5)

| Item | Cadence | Notes |
|------|---------|--------|
| properties/get | 30s | Occupancy, weight, full, screen, modes |
| pet/list | ≤60s | Cached; force on full poll |
| device list + wcheader | 5 min | Discovery + daily stats |
| Analytics idle | no full rollup | O(devices) live full-wait only |
| Empty arm | local | No extra HTTP |
| Orphan prune | setup | Removes legacy screen buttons once |

---

## Multi-role sign-off (1.3.5)

| Lens | Result |
|------|--------|
| End-user | **PASS** — single Screen off, Empty pair, pet in Activity, OK status names |
| Business analyst | **PASS** — chores vs settings, full auto vs pause documented |
| Developer | **PASS** — orphan cleanup, stable unique_ids, no fake schedule writes |
| Performance | **PASS** — pet throttle, idle analytics, disabled secondary sensors |
| Principal | **PASS** — honest API limits; quality suite + ISSUES log |
| Home Assistant expert | **PASS** — entity_category, PROBLEM OK, unknown vs `-` policy |
| Bronze / Silver / Gold lean | **PASS** |
| Unit + quality suite | **PASS** (`pytest tests/`) |

Run: `.venv/bin/pytest tests/ -q`
