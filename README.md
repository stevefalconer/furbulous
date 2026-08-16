# Furbulous — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant integration for **Furbulous** smart litter boxes, with HomeKit support.

## Attribution

| Role | Credit |
|------|--------|
| **Original author & core integration** | [Fabien Bounoir](https://github.com/fabienbounoir) ([original repo](https://github.com/FabienBounoir/furbulous-litterbox-home-assistant)) |
| **Localization, HA unit classes, region work** | [stevenfalconer](https://github.com/stevenfalconer) (this fork) |

This is a **modified fork** of the original project. Original copyright remains with Fabien Bounoir under the MIT License.

---

## Why this fork exists

The original integration hard-codes the **European** API endpoint and login region (`app.api.fr...`, `iso`/`area` EU). Furbulous accounts are region-scoped (US/Canada → Virginia, EU/UK → Frankfurt, etc.), so non-EU accounts get `invalid_auth` with correct credentials.

This fork currently defaults to the **US/Canada (Virginia)** endpoint and English UI so those accounts work. Multi-region selection at setup is the intended next step so one integration can serve all regions.

---

## Changes

### 1.1.2
- Removed remaining French entity names and state strings
- Daily uses: dimensionless count (no French `fois` unit)
- Weight: `SensorDeviceClass.WEIGHT` + grams (HA auto-converts to lb for US unit profiles)
- Duration: `SensorDeviceClass.DURATION` + seconds
- `SensorStateClass.MEASUREMENT` for weight, uses, and duration
- Neutral packaging (name **Furbulous**, not a US-only product name)
- French code comments → English

### 1.1.1
- API base URL → US (Virginia) endpoint as default
- Login `iso` / `area` → `"US"`
- `accept-language` → `"en"`
- UI strings and entity names → English

---

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. URL: `https://github.com/stevenfalconer/furbulous`
3. Category: **Integration**
4. Download → Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Furbulous**

### Manual

Copy `custom_components/furbulous/` into your HA `config/custom_components/`, then restart.

---

## Configuration

Enter the same email and password used in the official Furbulous app.

**Region note:** Default cloud endpoint is US/Canada. If login fails and your account is EU (or another region), the base URL in `const.py` / login `iso`/`area` must match your account region. A setup-time region dropdown is planned.

If US login still fails, try alternate base URLs in `custom_components/furbulous/const.py`, then restart:

```python
API_BASE_URL = "https://app.api.furbulouspet.com:1443"
# or
API_BASE_URL = "https://api.us.furbulouspet.com"
```

---

## Entities (overview)

**Switches (HomeKit):** Full auto mode, Do not disturb, Child lock  
**Binary sensors:** Cat in litter box (30s), Connected, Error, Waste bin full  
**Sensors:** Cat weight, Daily uses, Average duration, Error code, Pet info  
**Buttons:** Manual clean, Empty, Pack  

---

## Roadmap

- Region selector on the same setup screen as email/password
- HA translation files for UI languages (not hardcoded English)
- Keep API-native units + device classes (HA handles lb vs kg)

---

## License

MIT License — Copyright (c) 2025 Fabien Bounoir  

See [LICENSE](LICENSE). Original copyright and permission notice are retained in full.
