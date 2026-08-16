# Integration quality scale checklist (HACS custom)

Tracking against [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/).  
Status: **PASS** | **EXEMPT** (with reason). Not a core submission claim.

**Last reviewed:** 2026-08-16 (**v1.3.0** pre-push — BA + performance + Bronze/Silver/Gold)

Automated tests: `.venv/bin/pytest tests/ -q` (unit + real HA 2026.8.x harness).

---

## Bronze

| Rule | Status | Notes |
|------|--------|--------|
| config-flow | PASS | UI setup; `data_description` |
| test-before-configure | PASS | Auth + device list before create_entry |
| test-before-setup | PASS | `ConfigEntryAuthFailed` / `ConfigEntryNotReady` |
| unique-config-entry | PASS | `unique_id` = `email_region` |
| entity-unique-id | PASS | Stable ids for box + pet + analytics |
| has-entity-name | PASS | Base + analytics entities |
| runtime-data | PASS | api, dual coordinators, analytics engine |
| appropriate-polling | PASS | 5 min full (+pets); 30 s presence only |
| common-modules | PASS | api, regions, coordinator, entity, analytics |
| docs-high-level / install / removal | PASS | README + cat-lover tips |

---

## Silver

| Rule | Status | Notes |
|------|--------|--------|
| config-entry-unloading | PASS | Cancel flush tasks + force analytics persist |
| reauthentication-flow | PASS | reauth + display reset |
| entity-unavailable | PASS | Coordinator `last_update_success` |
| log-when-unavailable | PASS | Once down / once up |
| parallel-updates | PASS | `PARALLEL_UPDATES = 0` all platforms |
| integration-owner | PASS | CODEOWNERS + manifest |
| action-exceptions | PASS | `HomeAssistantError` + translations |

---

## Gold (lean)

| Rule | Status | Notes |
|------|--------|--------|
| devices | PASS | Box + pet `DeviceInfo` |
| entity-device-class | PASS | weight, duration, timestamp, connectivity, problem |
| entity-translations | PASS | strings + all locale files (new keys merged) |
| exception-translations | PASS | exceptions in strings |
| entity-category | PASS | diagnostic / config used correctly |
| diagnostics | PASS | Redacted + analytics counts |
| docs-known-limitations | PASS | Unknown pets, local history, Empty/litter tips |
| docs-data-update | PASS | Dual poll + analytics |
| docs-supported-functions | PASS | Entity tables + tips |
| reconfiguration-flow | PASS | reconfigure + unit clear |
| stale-devices | PASS | Prune boxes + pets not in snapshot |
| entity-disabled-by-default | PASS | Secondary analytics off by default |
| discovery | EXEMPT | Cloud login only |

---

## Platinum (not targeted)

| Rule | Status | Notes |
|------|--------|--------|
| async-dependency | EXEMPT | Inline aiohttp client |
| inject-websession | PASS | `async_get_clientsession` |
| strict-typing | EXEMPT | No full mypy gate |

---

## Pi / performance (pre-push)

| Practice | Status |
|----------|--------|
| Dual poll; pets not on 30s path | PASS |
| Idle presence: no full history rollup | PASS |
| Live full-wait O(devices) | PASS |
| Event index + 90d / 50k cap | PASS |
| Debounced flush + delayed retry if blocked | PASS |
| Force flush + cancel tasks on unload | PASS |
| State fingerprint (coordinator + analytics) | PASS |
| Restart restore open full / bag / litter | PASS |
| Weight calculated lb/kg (never g UI) | PASS |

---

## Cat-lover BA pre-push recommendations

| Recommendation | Status for 1.3.0 |
|----------------|------------------|
| Ship analytics (bag / full / litter / pets) | **Done** |
| Document Empty + Mark litter reset for good data | **Done** (README tips) |
| Restart-safe full wait / bag age | **Done** (restore from event log) |
| Hours-since bag/litter enabled by default | **Done** (primary overdue gauges) |
| Infer Empty/Pack done only on device (no HA) | **Deferred** — needs property discovery; full clear still tracked |
| Occupying pet without API field | **Unknown** by design until discovery |
| Blueprint automations (notify full 2h) | **Deferred** — optional post-1.3.0 polish |
| Human translation of new strings | **Partial** — keys present; EN text in non-EN packs until localized |

**BA ship decision:** Ready to push 1.3.0 with documented day-one habits. No further product blockers.

---

## Sign-off

| Lens | Result |
|------|--------|
| HA Bronze | **PASS** |
| HA Silver | **PASS** |
| HA Gold (lean) | **PASS** |
| Pi performance | **PASS** |
| Cat-lover BA | **Ship** with tips + known limits |

Run: `.venv/bin/pytest tests/ -q`
