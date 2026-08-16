# Furbulous — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

| | |
|--|--|
| **Domain** | `furbulous` |
| **Version** | 1.3.2 |
| **IoT class** | `cloud_polling` |
| **Min HA** | 2024.4.0 |
| **Issues** | [GitHub Issues](https://github.com/stevefalconer/furbulous/issues) |

---

## 1. What it is

Home Assistant **custom** (HACS) integration for **Furbulous** smart litter boxes. It polls the Furbulous **cloud** API so you can monitor and control devices from HA.

This is **not** an official Furbulous product and is **not** affiliated with or endorsed by Furbulous / the device vendor.

---

## 2. How it works

1. You sign in with the **same email and password** as the Furbulous mobile app.
2. You select the **account region** (must match the country chosen when you created the app account). Wrong region usually returns **invalid credentials**.
3. The integration authenticates to that region’s cloud host, lists devices, and stores a single API client on the config entry.
4. Two coordinators refresh data (entities never call the API themselves):
   - **~5 minutes:** device list, full properties, daily stats, **pet roster**  
   - **~30 seconds:** properties only for known devices (occupancy + full-bag edges)
5. Entities expose live control/status **and** local cat-lover analytics (visits, bag lifetime, litter intervals, time-to-clear full bags).  
6. History for 7d/30d metrics is stored **locally** (90-day event log)—the cloud does not provide month history.

---

## 3. Supported regions

| Region in setup | Typical countries | Cloud | Verification |
|-----------------|-------------------|-------|----------------|
| **United States / Canada** | US, CA | Virginia (`app.api.us…`) | **Verified** (maintainer) |
| **Europe / UK** | EU countries, GB | Frankfurt-style (`app.api.fr…`) | **Experimental** (upstream endpoint; not re-tested by this fork) |
| **Asia** | SG, JP, AU, TW, HK, KR, CN, … | Singapore family (`app.api.sg…`) | **Experimental** (host / login fields best-effort) |

Sharing and control only work **within the same cloud region**. There is no cross-region account use.

---

## 4. Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**  
2. URL: `https://github.com/stevefalconer/furbulous`  
3. Category: **Integration**  
4. Download → **Restart Home Assistant**  
5. Settings → Devices & Services → **Add Integration** → **Furbulous**

### Manual

1. Copy `custom_components/furbulous/` into `config/custom_components/`  
2. Restart Home Assistant  
3. Add the **Furbulous** integration  

### Prerequisites

- Home Assistant **2024.4** or newer  
- Furbulous app account and at least one litter box online  
- Device Wi‑Fi bind is typically **2.4 GHz only** (app / hardware limit)

---

## 5. Configuration parameters

| Field | Required | Stored in | Description |
|-------|----------|-----------|-------------|
| **Email** | Yes | Config entry **data** | Same as Furbulous app |
| **Password** | Yes | Config entry **data** | Same as Furbulous app |
| **Account region** | Yes | Config entry **data** | `us` / `eu` / `asia` |

There is **no options flow** for connection identity. Use **Reconfigure** or **Reauthenticate** to change email, password, or region.

Region default may be pre-selected from Home Assistant’s country setting when it maps cleanly; otherwise choose explicitly.

---

## 6. Data update

| Coordinator | Interval | What it refreshes |
|-------------|----------|-------------------|
| **Normal** | 5 minutes | Device list, full properties, daily stats, pets |
| **Presence** | 30 seconds | Properties for known devices only (occupancy / full edges) |

- Requires internet and Furbulous cloud availability.  
- On failure, entities go **unavailable**; the integration logs once when down and once when restored.  
- Failed requests use short exponential backoff (no request storms).  
- New litter boxes appear after the next normal poll **without** reloading the integration. Devices that disappear are pruned from the device registry (pet devices are kept while still on the account).  
- **Analytics** run from coordinator deltas + Empty/Pack/litter-reset buttons (no extra cloud history API).

**Load (1 device, idle):** ~**180** cloud HTTP calls/hour  
(~120 presence property polls + ~60 pet-list/hour at 1 min + ~36 full-path calls for list/stats/pets).

---

## 7. Entities / functions

### Litter box (per device)

| Platform | Entities |
|----------|----------|
| Binary sensor | Cat in litter box; Waste bin full; Cover open; Drawer not in place; Connected*; Child lock*; Energy saving active* |
| Sensor (live) | Cat weight (lb/kg); Daily uses; Average daily duration; Error*; Firmware*; Hand mode*; Completion status*; Uses/duration vs yesterday‡ |
| Sensor (analytics) | **Last visitor**; **Last visit time** (local in UI); **Last visit weight** (lb/kg); Occupying pet; Visits 7d/30d; Time full; bag/litter/pack metrics |
| Switch | Full auto mode; **Do not disturb** (on/off; schedule in app); **Energy saving** (display dim on standby; on/off); Child lock† |
| Button | Manual clean; Pause; Resume; Empty; Pack; **Mark litter reset**; **Screen off** / **Screen on** (blank display for automations) |
| Select | Cleaning delay† |

### Pets (per cat from account roster)

| Platform | Entities |
|----------|----------|
| Sensor | Visits 7d / 30d; Avg visit duration 30d; Favorite litter box; Last seen |

\* Diagnostic · † Config · ‡ Disabled by default  

**Unknown** is used when a visitor cannot be identified. Averages with no samples show **none** / empty (not a fake zero).  

### Cat-lover tips (get great analytics from day one)

1. Prefer **Last visitor**, **Last visit time**, and **Last visit weight** — filled after each detected use (name/weight from API when present). Empty values show as **`-`**.  
2. **Occupying pet** is only set while a cat is in the box; otherwise **`-`** (never the previous visitor).  
3. **Properties** (occupancy, weight, pet name fields, full/errors, display mode) refresh about every **30 seconds**. The **pet roster** (`pet/list`) refreshes at most every **1 minute**. Daily stats and device discovery stay on the **5‑minute** poll.  
4. **Screen off** / **Screen on** buttons blank or restore the display (same API as Energy saving) so automations can keep the screen off unless bag full / errors.  
5. **Empty from HA** for bag lifetime; **Mark litter reset** after adding litter.  
6. **Do not disturb** = stop cleaning (on/off in HA; schedule times in the app).  
7. After upgrade, **restart HA** so weight shows **lb** / **kg**.

---

## 8. Units

- **Weight:** Cloud API reports **grams**. The integration **calculates** the sensor state from your Home Assistant **unit system** (Settings → System → General):  
  - **US Customary** → state in **lb**  
  - **Metric** → state in **kg**  
  Device class remains `WEIGHT` with one decimal of precision.  
- **Duration:** native **seconds** + `SensorDeviceClass.DURATION`.  
- No login-time unit picker.

This avoids relying on HA’s sticky entity-registry conversion for weight (which often left grams on US installs). After upgrading to **1.2.2+**, reload or restart once so sticky `g` locks are cleared.

---

## 9. Internationalization

- **UI language** follows **Home Assistant** (Settings → System → General → Language). Entity and setup strings use `translation_key` / translation files.  
- **Account region** is independent of UI language (e.g. EU region + English HA is valid).  
- Starting packs: en, fr, de, es, it, pt-BR, ja, ko, zh-Hans, zh-Hant, ru.

**Adding a translation (contributors):** copy `custom_components/furbulous/translations/en.json` to a new locale file (e.g. `nl.json`), translate values only, keep keys identical to `strings.json`, open a PR.

---

## 10. Resets, reauth, and recovery

| Action | When to use | How |
|--------|-------------|-----|
| **Reauthentication** | Password changed, token fails, or HA prompts reauth | Complete the reauth form (email / password / region). Devices are retained when possible. Clears sticky unit/name overrides. |
| **Reconfigure** | Change region or account without deleting the integration | Devices & Services → Furbulous → **Reconfigure**. Clears sticky unit/name overrides, then reloads. |
| **Reload** | Soft refresh after a transient glitch | Devices & Services → Furbulous → ⋮ → **Reload** |
| **Remove & re-add** | Corrupt entry, unique_id/region confusion, or last resort | Delete integration, then add again. Unique id is `email_region`—same email on two regions can be two entries. |
| **Failed setup** | Cannot finish add / setup error | **invalid_auth:** check password **and region** first. **cannot_connect:** network/DNS/TLS or cloud down. |
| **Entity unavailable** | Coordinator/API failure or offline device | Not necessarily a cat/litter problem—check internet, cloud, reauth if prompted. |

---

## 11. Known limitations

- Region-locked accounts; no cross-region sharing or control.  
- EU / Asia are **experimental** in this fork.  
- Vendor API is reverse-engineered and can change without notice.  
- Cloud only—no local/LAN control in this integration.  
- App Wi‑Fi provisioning is typically 2.4 GHz only.  
- Password is stored in the config entry (protect HA backups).  

---

## 12. Troubleshooting

| Symptom | What to try |
|---------|-------------|
| Invalid credentials | Confirm app password; **select the correct region** |
| Experimental region fails | Open an issue with app registration country + error text (no passwords) |
| No devices | Confirm boxes online in the app; wait for a full poll |
| Stale data | Wait for next poll interval; Reload; check cloud status |
| Weight stuck on grams | Reconfigure once, or set entity unit to lb/kg; set HA unit system |
| Rate limit / flaky cloud | Integration backs off automatically; avoid rapid re-add loops |

---

## 13. Diagnostics and bug reports

**Defect channel:** [GitHub Issues](https://github.com/stevefalconer/furbulous/issues)

**Include:**

- Home Assistant version  
- Integration version (1.2.0)  
- Account **region** selected  
- Steps to reproduce  
- Symptom (auth, no devices, unavailable entities, wrong units)  
- Redacted logs or **Download diagnostics** from the device/integration (secrets are redacted—still do not paste passwords)

**Never** post passwords, tokens, or full auth headers.

---

## 14. Development / tests

```bash
cd furbulous
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

- Unit tests mock HTTP (no live Furbulous credentials).  
- Full HA tests use `pytest-homeassistant-custom-component` (listed in `requirements-dev.txt`).  
- Quality checklist: [quality_scale.md](quality_scale.md)

---

## 15. Attribution and license

| Role | Credit |
|------|--------|
| Original author & core integration | [Fabien Bounoir](https://github.com/fabienbounoir) ([original repo](https://github.com/FabienBounoir/furbulous-litterbox-home-assistant)) |
| Multi-region, i18n, async client, quality work | [stevefalconer](https://github.com/stevefalconer) (this fork) |

MIT License — see [LICENSE](LICENSE). Original copyright remains with Fabien Bounoir.

---

## 16. Support policy

| Supported | Best-effort / experimental |
|-----------|----------------------------|
| US/Canada cloud path | EU / Asia cloud paths |
| Documented install, config, recovery | Community translations |
| Issues with required bug details | Feature requests without API evidence |

Maintenance is **community / best-effort**. There is no SLA. Prefer issues with diagnostics over private messages. Do not request the maintainer to obtain foreign-region accounts for free multi-region QA.

---

## Upgrading from 1.1.2

1. Install 1.2.0 → restart HA.  
2. Entries migrate to **region = us** automatically.  
3. Confirm devices and weight unit; use **Reconfigure** for non-US accounts.  

See [CHANGELOG.md](CHANGELOG.md) and [DEPLOYMENT_NOTES_1.2.0.md](DEPLOYMENT_NOTES_1.2.0.md).
