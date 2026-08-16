# Integration quality scale checklist (HACS custom)

Tracking against [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/).  
Status: **PASS** | **EXEMPT** (with reason). Not a core submission claim.

**Last reviewed:** 2026-08-16 (**v1.3.9**)

Automated tests:

```bash
.venv/bin/pytest tests/ -q
.venv/bin/pytest tests/quality/ -q
```

Prompts: [tests/quality/PROMPTS.md](tests/quality/PROMPTS.md) · Issues: [tests/quality/ISSUES.md](tests/quality/ISSUES.md)  
Adoption: [docs/CAT_PARENT_GUIDE.md](docs/CAT_PARENT_GUIDE.md) · Power: [docs/POWER_USER.md](docs/POWER_USER.md)

---

## Bronze

| Rule | Status | Notes |
|------|--------|--------|
| config-flow | PASS | UI setup; data_description |
| test-before-configure | PASS | Auth + device list before create_entry |
| test-before-setup | PASS | ConfigEntryAuthFailed / ConfigEntryNotReady |
| unique-config-entry | PASS | unique_id email_region |
| entity-unique-id | PASS | Cat-parent slug scheme `furbulous_{id}_{slug}` (1.3.7) |
| has-entity-name | PASS | translation_key names |
| runtime-data | PASS | api, dual coordinators, analytics |
| appropriate-polling | PASS | 30s / ≤60s pets / 5 min full |
| common-modules | PASS | analytics, events, ux, schedule_props |
| docs-high-level / install / removal | PASS | README + cat parent guide |

---

## Silver

| Rule | Status | Notes |
|------|--------|--------|
| config-entry-unloading | PASS | Analytics flush |
| reauthentication-flow | PASS | reauth |
| entity-unavailable | PASS | last_update_success |
| log-when-unavailable | PASS | Once down / once up |
| parallel-updates | PASS | PARALLEL_UPDATES = 0 |
| integration-owner | PASS | CODEOWNERS |
| action-exceptions | PASS | empty_not_confirmed plain English |

---

## Gold (lean)

| Rule | Status | Notes |
|------|--------|--------|
| devices | PASS | Box + pet |
| entity-device-class | PASS | weight, duration, connectivity, problem |
| entity-translations | PASS | Cat-parent English names in packs |
| exception-translations | PASS | exceptions |
| entity-category | PASS | CONFIG settings; Controls chores |
| diagnostics | PASS | Redacted |
| docs-known-limitations | PASS | Schedule write in app; multi-cat weight |
| docs-data-update | PASS | Dual poll |
| docs-supported-functions | PASS | README + guides + events |
| reconfiguration-flow | PASS | reconfigure |
| stale-devices | PASS | Prune |
| entity-disabled-by-default | PASS | Secondary set |
| discovery | EXEMPT | Cloud login |

---

## Multi-role sign-off (1.3.6)

| Lens | Result |
|------|--------|
| Casual cat parent | **PASS** — plain names + CAT_PARENT_GUIDE |
| Multi-cat household | **PASS** — Last cat/visit, bag/litter age |
| Power automator | **PASS** — events + attrs + stable unique_ids |
| HA usability | **PASS** — categories, PROBLEM OK, progressive disclosure |
| General app UX | **PASS** — safety empty, jargon reduced |
| Business analyst | **PASS** — chore outcomes mapped |
| Performance | **PASS** — unchanged poll budget + events cheap |
| Principal | **PASS** — no capability removal |
| Bronze / Silver / Gold lean | **PASS** |

Run: `.venv/bin/pytest tests/ -q`
