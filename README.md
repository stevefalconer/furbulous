# Furbulous — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

| | |
|--|--|
| **Domain** | `furbulous` |
| **Version** | 1.3.12 |
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
   - **~5 minutes:** device list, full properties, daily stats, pets (force refresh)  
   - **~30 seconds:** properties (occupancy, weight, full/errors, modes); pet roster at most every **1 minute**
5. **Multi-cat identity** (app-style): match visit weight to the closest cat on the account roster (or learned weights).  
6. Entities expose last visit (cat / time / weight), chore analytics, and controls.  
7. Day/7d/30d history is **local** (90-day event log)—the cloud does not expose month history.

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
- A **dedicated Furbulous account** for Home Assistant (recommended)  
- At least one litter box online  
- Device Wi‑Fi bind is typically **2.4 GHz only** (app / hardware limit)

The Furbulous **phone app appears to allow only one login at a time**. If you put your everyday app email/password into HA, each HA login or token refresh can **sign the app out** and you will keep re-entering the password. Create a second Furbulous account, share the boxes to it, and use **only that account** in this integration.

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
| **Normal** | 5 minutes | Device list, full properties, daily stats, pets (force) |
| **Presence** | 30 seconds | Properties (occupancy, weight, errors, modes); pets ≤1/min cache |

- Requires internet and Furbulous cloud availability.  
- On failure, entities go **unavailable**; the integration logs once when down and once when restored.  
- Failed requests use short exponential backoff (no request storms).  
- New litter boxes appear after the next normal poll **without** reloading the integration. Boxes/pets that disappear are pruned from the device registry.  
- **Analytics** run from poll edges + Empty/Pack/litter-reset buttons (no vendor visit-history API).

**Load (1 device, idle):** ~**180** cloud HTTP calls/hour  
(~120 property polls + ~60 pet-list/hour + full-path list/stats).

---

## 7. Entities / functions

**Start here if you care for cats, not code:** [docs/CAT_PARENT_GUIDE.md](docs/CAT_PARENT_GUIDE.md)  
**Automations / events / raw fields:** [docs/POWER_USER.md](docs/POWER_USER.md)  
**UX review (personas + experts):** [docs/UX_REVIEW_1.3.6.md](docs/UX_REVIEW_1.3.6.md)

### Litter box (per device) — friendly names

| Platform | Entities | Device page section |
|----------|----------|---------------------|
| Binary sensor | **Cat inside**; **Needs emptying** / **Cover open** / **Drawer out of place** (OK or Problem); Online*; Child lock on*; Screen is off*‡ | Sensors / Diagnostic |
| Sensor (live) | Cat weight; **Uses today**; Average visit today; Error message*; Firmware*; **What the box is doing***; **Clean cycle status***; day-over-day‡ | Sensors / Diagnostic |
| Time | **Screen schedule start** / **Screen schedule end**; **Quiet hours start** / **Quiet hours end** (writable daily window) | **Configuration** |
| Sensor (analytics) | **Last cat**; **Last visit** (`H:MM M-D`); Last visit time/weight; **Who is inside**; Visits (7/30 days); **Bag age** / **Litter age**; bag/litter/pack metrics | Sensors |
| Switch | **Auto-clean after visits**; **Quiet hours**; Child lock | **Configuration** |
| Switch | **Empty — confirm ready** (safety) | **Controls** |
| Button | **Clean now**; Pause / Resume cleaning; **Empty all litter** (needs confirm); **Seal waste bag**; **I refilled the litter** | **Controls** |
| Select | **Screen mode** (Always on / Scheduled); **Auto-clean minutes before** | **Configuration** |

### Pets (per cat from account roster)

| Platform | Entities |
|----------|----------|
| Sensor | Visits (7 / 30 days); Visit length average (30 days); Favorite litter box; Last seen |

\* Diagnostic  

**Controls** = chores. **Configuration** = preferences (including schedule times).  

**Entity unique_ids** (1.3.7+) use cat-language slugs, e.g.  
`furbulous_{device_id}_last_cat`, `_needs_emptying`, `_empty_waste`, `_bag_age_hours`  
(see `entity_ids.py`). Display names match the same vocabulary.

### Auto-clean vs Pause / Resume

| Control | What it does |
|---------|----------------|
| **Auto-clean after visits** | After a visit, the box **starts cleaning by itself**. Off = only when you press **Clean now**. |
| **Pause cleaning** | Stops a cycle that is **already running**. |
| **Resume cleaning** | Continues a **paused** cycle. |

### Empty safety

1. Turn **ON** **Empty — confirm ready** (drum closed).  
2. Within **90 seconds**, press **Empty all litter**.  
3. Without that arm, Empty all litter is blocked.  

### Status sensors (OK / Problem)

| Entity | **OK** | **Problem** | Code |
|--------|--------|-------------|------|
| Needs emptying | Bag has room | Empty / seal soon | 16 or 32 |
| Cover open | Lid / cover on | Put the lid back on | 128 or **512** (live lid-off) |
| Drawer out of place | Always OK | Cloud does **not** report drawer-out | — |
| Trash door jammed | Waste door clear | Clump on the waste door (E4). Scoop it off, press **OK on the box** | **524288** |

### What the box is doing

**Idle** when `workstatus=0` (even if the last button still shows in attributes). **Cleaning** / **Packing bag** / **Resetting litter** follow live `workstatus`. Sticky `handMode` is in attributes only.

### Clean cycle status

Vendor `completionStatus` — friendly labels + **raw** attribute. Confirm on your unit via diagnostics if automating.

### Empty states: `-` vs unknown

| Kind | Display |
|------|---------|
| Text | **`-`** |
| Counts | **0** |
| Weight / duration / timestamp | HA **unknown** until first real value |

### Screen mode & Quiet hours windows

- **Screen mode** = **Always on** (panel stays lit, including overnight) or **Scheduled / Eco** (blank **inside** **Screen schedule start**–**end**, house-local minutes).
- A button **always wakes** a dark Eco panel. **Screen is off** is schedule *intent*, not live pixels.
- **Quiet hours** only applies inside **Quiet hours start**–**Quiet hours end**. Set both times.

Times are written to the cloud API (not app-only). House-local, not UTC / Virginia.

### Power-user events (capabilities kept)

Bus events for automations (do not depend on display names):  
`furbulous_visit_ended`, `furbulous_waste_full`, `furbulous_waste_cleared`, `furbulous_bag_replaced`, `furbulous_pack`, `furbulous_litter_reset` — details in [POWER_USER.md](docs/POWER_USER.md).

### Cat-lover tips

1. Set accurate **pet weights in the Furbulous app** (multi-cat closest-weight match).  
2. Prefer **Last cat** / **Last visit** after a use; **Who is inside** only while occupied.  
3. **Bag age** and **Litter age** are your “is it overdue?” gauges — press **I refilled the litter** after topping up. Bag age also restarts when a bag-full error clears in the cloud.  
4. Properties ~**30s**; pets ≤**1 min**; full stats **5 min**.

---

## 8. Units

- **Weight:** Cloud API reports **grams**. The integration **calculates** the sensor state from your Home Assistant **unit system** (Settings → System → General):  
  - **US Customary** → state in **lb**  
  - **Metric** → state in **kg**  
  Device class remains `WEIGHT` with one decimal of precision.  
- **Duration:** native **seconds** + `SensorDeviceClass.DURATION`.  
- No login-time unit picker.

After upgrade, **restart Home Assistant** once so weight units and new entities load cleanly.

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
- Integration version (see `manifest.json` / HACS, e.g. **1.3.12**)  
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
# Persistent bronze / silver / gold / performance / UAT suite:
pytest tests/quality/ -v
```

- Unit tests mock HTTP (no live Furbulous credentials).  
- Full HA tests use `pytest-homeassistant-custom-component` (listed in `requirements-dev.txt`).  
- Quality checklist: [quality_scale.md](quality_scale.md)  
- Repeatable agent prompts + issue log: [tests/quality/PROMPTS.md](tests/quality/PROMPTS.md), [tests/quality/ISSUES.md](tests/quality/ISSUES.md)

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

## Upgrading

1. Update via HACS (or replace `custom_components/furbulous/`) → **restart HA**.  
2. Confirm **unit system** (US → weight in **lb**; Metric → **kg**).  
3. Set accurate **pet weights in the Furbulous app** for multi-cat matching.  
4. For Empty: use **Empty — confirm ready**, then **Empty all litter** within 90 seconds.  
5. After upgrade: **restart once** so names refresh and orphan Screen buttons are removed.  
6. New here? Read [docs/CAT_PARENT_GUIDE.md](docs/CAT_PARENT_GUIDE.md).

See [CHANGELOG.md](CHANGELOG.md) for full history. Notes for the 1.1.x→1.2.0 migration: [DEPLOYMENT_NOTES_1.2.0.md](DEPLOYMENT_NOTES_1.2.0.md).
