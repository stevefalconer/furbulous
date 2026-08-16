# Changelog

All notable changes to this fork are documented here.

## 1.2.1 — 2026-08-16

### Fixed

- **Cat weight in pounds:** Home Assistant does not auto-convert weight `g`→`lb` from the unit system (unlike temperature). The weight sensor now **suggests** `hass.config.units.mass_unit` (lb under US Customary). Reconfigure/reauth and the upgrade path force a registry refresh of that suggested unit so existing installs pick up lb without a manual entity edit (manual entity unit → lb still works anytime).

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
