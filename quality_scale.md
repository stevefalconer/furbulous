# Integration quality scale checklist (HACS custom)

Tracking against [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/).  
Status: **PASS** | **EXEMPT** (with reason). Not a core submission claim.

## Bronze

| Rule | Status | Notes |
|------|--------|--------|
| config-flow | PASS | UI setup; data_description |
| test-before-configure | PASS | Auth + device list before create_entry |
| test-before-setup | PASS | ConfigEntryAuthFailed / ConfigEntryNotReady |
| unique-config-entry | PASS | unique_id `email_region` |
| entity-unique-id | PASS | Stable unique_ids |
| has-entity-name | PASS | Entity base |
| runtime-data | PASS | FurbulousRuntimeData |
| appropriate-polling | PASS | 5 min full / 30 s presence |
| common-modules | PASS | api, regions, coordinator, entity |
| docs-high-level / install / removal | PASS | README |

## Silver

| Rule | Status | Notes |
|------|--------|--------|
| config-entry-unloading | PASS | async_unload_entry |
| reauthentication-flow | PASS | reauth + display reset |
| entity-unavailable | PASS | last_update_success |
| log-when-unavailable | PASS | Once down / once up |
| parallel-updates | PASS | PARALLEL_UPDATES = 0 |
| integration-owner | PASS | CODEOWNERS + manifest |
| action-exceptions | PASS | HomeAssistantError on set failures |

## Gold (priority)

| Rule | Status | Notes |
|------|--------|--------|
| devices | PASS | DeviceInfo |
| entity-device-class | PASS | weight, duration, connectivity, … |
| entity-translations | PASS | strings + translations/* |
| exception-translations | PASS | exceptions in strings |
| entity-category | PASS | diagnostic / config |
| diagnostics | PASS | Redacted secrets |
| docs-known-limitations | PASS | README |
| docs-data-update | PASS | README |
| docs-supported-functions | PASS | README entities |
| reconfiguration-flow | PASS | reconfigure + display reset |
| stale-devices | PASS | Prune on full poll |
| entity-disabled-by-default | EXEMPT | No high-noise primary entities |
| discovery | EXEMPT | Cloud login only |

## Platinum (not targeted)

| Rule | Status | Notes |
|------|--------|--------|
| async-dependency | EXEMPT | Inline aiohttp client; no separate PyPI lib yet |
| inject-websession | PASS | async_get_clientsession |
| strict-typing | EXEMPT | Not full mypy gate |

Last reviewed: 2026-08-15 (v1.2.0).
