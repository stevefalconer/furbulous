# Integration quality scale checklist (HACS custom)

Tracking against [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/).  
Status: **PASS** | **EXEMPT** (with reason). Not a core submission claim.

**Last reviewed:** 2026-08-16 (**v1.3.2** — last-visit UX, screen buttons, pet/list 1 min throttle)

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
| appropriate-polling | PASS | 30s properties; ≤1 min pets; 5 min list/stats |
| common-modules | PASS | api, coordinator, analytics, entity |
| docs-high-level / install / removal | PASS | README |

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
| action-exceptions | PASS | HomeAssistantError + translations |

---

## Gold (lean)

| Rule | Status | Notes |
|------|--------|--------|
| devices | PASS | Box + pet devices |
| entity-device-class | PASS | weight, duration, timestamp, problem, … |
| entity-translations | PASS | strings + locale packs |
| exception-translations | PASS | exceptions in strings |
| entity-category | PASS | diagnostic / config |
| diagnostics | PASS | Redacted + analytics counts |
| docs-known-limitations | PASS | DND schedule in app; `-` empties; local history |
| docs-data-update | PASS | Dual poll + pet throttle documented |
| docs-supported-functions | PASS | Entity tables + tips |
| reconfiguration-flow | PASS | reconfigure |
| stale-devices | PASS | Boxes + pets pruned |
| entity-disabled-by-default | PASS | Secondary analytics off by default |
| discovery | EXEMPT | Cloud login only |

---

## Performance review (v1.3.2)

| Item | Decision | Functionality impact |
|------|----------|----------------------|
| `properties/get` @ 30s | **Keep** | Visit edges, weight, full, screen/energy, errors |
| `pet/list` @ **≤60s** | **Throttle** (was every 30s) | Roster names lag ≤1 min; visit identity still from properties @ 30s |
| Device list @ 5 min | **Keep** | New boxes / online lag up to 5 min |
| `wcheader` @ 5 min | **Keep** | Daily uses lag up to 5 min |
| Analytics idle path | **Keep** | No full rollup on quiet 30s ticks |
| Flush debounce + delayed retry | **Keep** | Events persist without SD thrash |
| Empty text `-` | **Keep** | Numerics still `None` for device classes |
| Screen on/off buttons | **Keep** | Same property as energy saving; +2 buttons |

**Functionality change from pet throttle:** multi-cat **device names** from roster can lag 1 minute after rename in app; **last visit / occupying / weight** still use 30s properties.

---

## Cat-lover BA sign-off (v1.3.2)

| Need | Status |
|------|--------|
| Last cat / weight / local time after use | PASS |
| Empty shows `-` not Unknown | PASS (text); numerics None |
| Occupying blank when empty | PASS |
| Screen blank via automation | PASS (Screen off/on) |
| Energy saving + DND on/off | PASS; schedules in app |
| Fast path for visit signals | PASS (30s properties) |
| Pet list not over-polled | PASS (1 min) |

---

## Sign-off

| Lens | Result |
|------|--------|
| Bronze | **PASS** |
| Silver | **PASS** |
| Gold lean | **PASS** |
| Performance | **PASS** (pet list 1 min) |
| Unit + HA tests | Required green before tag |

Run: `.venv/bin/pytest tests/ -q`
