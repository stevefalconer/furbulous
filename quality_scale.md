# Integration quality scale checklist (HACS custom)

Tracking against [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/).  
Status: **PASS** | **EXEMPT** (with reason). Not a core submission claim.

**Last reviewed:** 2026-08-16 (**v1.3.4**)

Automated tests: `.venv/bin/pytest tests/ -q` (unit + real HA harness).

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
| common-modules | PASS | api, coordinator, analytics, pet_match |
| docs-high-level / install / removal | PASS | README current for 1.3.4 |

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
| entity-category | PASS | diagnostic for support sensors; controls uncategorized |
| diagnostics | PASS | Redacted + analytics counts |
| docs-known-limitations | PASS | Multi-cat weight gaps, DND schedule in app |
| docs-data-update | PASS | Dual poll + pet throttle |
| docs-supported-functions | PASS | README entities + empty safety + multi-cat |
| reconfiguration-flow | PASS | reconfigure |
| stale-devices | PASS | Boxes + pets pruned |
| entity-disabled-by-default | PASS | Secondary analytics off by default |
| discovery | EXEMPT | Cloud login only |

---

## Performance (1.3.4)

| Item | Cadence | Notes |
|------|---------|--------|
| properties/get | 30s | Occupancy, weight, full, screen, modes |
| pet/list | ≤60s | Cached; force on full poll |
| device list + wcheader | 5 min | Discovery + daily stats |
| Analytics idle | no full rollup | O(devices) live full-wait only |
| Empty arm | local | No extra HTTP |

---

## Sign-off

| Lens | Result |
|------|--------|
| Bronze | **PASS** |
| Silver | **PASS** |
| Gold lean | **PASS** |
| Multi-cat weight match tests | **PASS** (realistic 5-cat noise) |

Run: `.venv/bin/pytest tests/ -q`
