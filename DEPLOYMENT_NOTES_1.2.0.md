# Deployment notes: 1.1.2 → 1.2.0

**Target:** HACS custom repository `stevefalconer/furbulous`  
**Date:** 2026-08-15  
**Min Home Assistant:** 2024.4.0  

## Who this is for

Maintainers shipping **1.2.0** after a working **1.1.2** US install.

## What users should do

1. Update the integration (HACS or replace `custom_components/furbulous/`).
2. **Restart Home Assistant.**
3. Open Furbulous devices — entities should return.
4. Existing entries auto-migrate to **region = US** and unique id `email_us`.
5. Confirm cat weight unit (if stuck on **g**, set entity unit to **lb** or **kg** once).
6. Optional: Settings → Devices & Services → Furbulous → **Reconfigure** to change region/credentials.
7. Optional: Download **diagnostics** from a device page (secrets redacted).

## What changed (product-facing)

| Area | 1.1.2 | 1.2.0 |
|------|-------|-------|
| Region | Hardcoded US | Selector: US / EU / Asia |
| HTTP | `requests` + executor | `aiohttp` + shared HA session |
| Polling | Full fetch on 30s *and* 5 min | 5 min full; 30 s **presence only** |
| Entity names | Hardcoded English | `translation_key` + language packs |
| Weight | Grams + device class | Same (native g); HA converts; 1 decimal suggestion |
| Auth recovery | Manual re-add | Reauth + reconfigure flows |
| Diagnostics | None | Config entry diagnostics (redacted) |
| Docs | Minimal | Support model, limitations, removal, polling |

## Region behavior (data correctness)

| Region id | Base host pattern | Login `iso` / `area` | Label |
|-----------|-------------------|----------------------|--------|
| `us` | `app.api.us.furbulouspet.com` | `US` / `US` | Supported |
| `eu` | `app.api.fr.furbulouspet.com` | `DE` / `EU` (upstream) | Experimental |
| `asia` | `app.api.sg.furbulouspet.com` | `SG` / `ASIA` (placeholder) | Experimental |

Wrong region → `invalid_auth`. Do not claim EU/Asia as verified.

## Risk checklist before publish

- [ ] US login still works on your HA after upgrade  
- [ ] Weight displays in expected unit (or one-time unit fix applied)  
- [ ] Cat-in-box updates within ~30–60 s  
- [ ] Manual clean button works  
- [ ] New litter box appears without reloading integration (after next 5‑min poll)  
- [ ] `pytest -v` passes (unit + HA harness)  
- [ ] README + CHANGELOG + quality_scale.md committed  
- [ ] Tag `v1.2.0` on GitHub for HACS  

## Release notes (for GitHub tag)

Suggested tag message:

```
v1.2.0 — multi-region, async API, HA quality pass

- Region selector (US verified; EU/Asia experimental)
- aiohttp + split polling (5 min / 30 s presence)
- Entity translations, reauth/reconfigure, diagnostics
- Dynamic devices; sticky unit/name reset on reconfigure
- Full README recovery/docs; issue templates; pytest suite
```

## Rollback

Reinstall 1.1.2 files and restart. Config entry v2 may keep `region` key (harmless for 1.1.2 if ignored). Prefer re-adding the integration if setup fails after rollback.

## Files added since 1.1.2 (high level)

- `regions.py`, `weight.py`, `models.py`, `coordinator.py`, `diagnostics.py`, `entity.py`, `icons.json`  
- `translations/*` (11 locales)  
- `tests/`, `requirements-dev.txt`, `CHANGELOG.md`, `CODEOWNERS`  

## Not in this release

- Core Home Assistant PR (still HACS custom)  
- Maintainer-verified EU/Asia live auth  
- aiohttp rewritten as a separate PyPI library  
