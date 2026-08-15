# Furbulous Cat - Home Assistant Integration (US Edition)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant integration for **Furbulous Cat** smart litter boxes, with HomeKit support.

## Attribution

| Role | Credit |
|------|--------|
| **Original author & core integration** | [Fabien Bounoir](https://github.com/fabienbounoir) ([original repo](https://github.com/FabienBounoir/furbulous-litterbox-home-assistant)) |
| **US region support & American English localization** | Community contribution (this fork) |

This is a **modified fork** of the original project. All original copyright remains with Fabien Bounoir under the MIT License. This edition only adds US/Canada cloud server support and translates the UI/entity names to American English.

Upstream issue/PR for multi-region support is intended so this fork can eventually be retired or merged.

---

## Why this fork exists

The original integration hard-codes the **European (France)** API endpoint and login region:

- Base URL: `https://app.api.fr.furbulouspet.com:1443`
- Login payload: `"iso": "DE"`, `"area": "EU"`

Furbulous uses **region-specific cloud servers**. United States and Canada accounts live on the **Virginia** server, so the same credentials that work in the official app fail with "invalid Auth" against the EU endpoint.

This edition points at the US server and uses US region values at login.

---

## Changes in 1.1.1-us

- API base URL → US (Virginia) endpoint
- Login `iso` / `area` → `"US"`
- `accept-language` → `"en"`
- UI strings (`strings.json`) → American English
- Entity display names → English
- Comments and docs → English
- `hacs.json` country → `US`

---

## Installation (immediate use)

### Manual (fastest)

1. Copy `custom_components/furbulous/` into your Home Assistant  
   `config/custom_components/` folder.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Furbulous Cat**
4. Enter the same email/password that works in the official Furbulous app.

### Via HACS (after you push this to your GitHub)

1. HACS → Integrations → ⋮ → Custom repositories  
2. Add **your** repository URL, category **Integration**  
3. Download, restart, then add the integration as above.

---

## If authentication still fails

The US endpoint is inferred from the original `fr` pattern. If login still fails, edit `custom_components/furbulous/const.py` and try:

```python
API_BASE_URL = "https://app.api.furbulouspet.com:1443"
# or
API_BASE_URL = "https://api.us.furbulouspet.com"
```

Then restart Home Assistant and try again.

---

## Main entities

**Switches (HomeKit):** Full auto mode, Do not disturb, Child lock  

**Binary sensors:** Cat in litter box (30s updates), Connected, Error, Waste bin full  

**Sensors:** Cat weight, Daily uses, Average duration, Error code, Pet info  

**Buttons:** Manual clean, Empty, Pack  

---

## Planned improvement (for upstream)

A proper multi-region config flow (region dropdown → correct base URL + login `iso`/`area`) would let one integration serve US, EU, and other regions. That change is intended to be offered back to the original author via issue/PR.

---

## License

MIT License — Copyright (c) 2025 Fabien Bounoir  

See [LICENSE](LICENSE). The original copyright notice and permission notice are retained in full.
