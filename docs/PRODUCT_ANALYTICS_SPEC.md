# Furbulous HA — Cat-lover analytics product specification

**Audience:** Product, implementers (HA integration), and reviewers  
**Status:** **Implemented in 1.3.x** (see README + CHANGELOG; this doc remains the design reference)  
**Integration baseline:** **1.3.4** — dual poll, local analytics, multi-cat weight match, last-visit UX, empty safety  
**Last updated:** 2026-08-16  

---

## 0. How to use this document

| Reader | Start here |
|--------|------------|
| Product / cat lover | §1 vision, §2 glossary, **§3A API visibility**, §5 chore journeys, §6 pet journeys, §12 acceptance |
| Developer implementing analytics + entities | §3 architecture, **§3A–3B**, §4 events, §5–7, §8–11 NFRs/phases |
| Discovery / reverse engineering | §9 discovery checklist, §13 open decisions |

**Source-of-truth rules:**

1. Metrics described as “last month / average between X” are **local event analytics (Layer B)** unless discovery finds a vendor history API. Do not invent cloud endpoints.  
2. **Every read and read/write API element that a cat-lover BA judges useful for Home Assistant automations or cat-care UX must be visible in the integration**—as a proper HA entity (or deliberate entity attribute), not left only in diagnostics or dead client code. See **§3A**.

---

## 1. Product vision

Help multi-cat households **understand health and household chore patterns** from Furbulous activity—not just “is the box online?”

### 1.1 North-star outcomes for cat lovers

1. Know **which cat** used the box (or **Unknown**).  
2. See **weight and visit habits** per cat (today / 7 days / 30 days).  
3. See **which box each cat prefers**.  
4. Know **when bags and litter need attention**:  
   - how long bags last between replacements,  
   - how long between adding litter and the next reset (and averages),  
   - how long a **full** bag sits before someone takes it out (last + averages).  
5. Get **calm, trustworthy** metrics (clear **Unknown** / **None**, no fake precision).  
6. Use **Home Assistant as the home for Furbulous control + insight**: anything the cloud API exposes that helps automations or cat care should appear in HA (read and read/write), following HA best practices so the integration stays **fast, lean, and delightful**.

### 1.2 Why chores matter as much as visits

Cat lovers do not only ask “how often did Mochi go?” They also ask:

- “This bag lasted **how many days** this time?”  
- “We usually last **~X days** between bag changes—are we overdue?”  
- “I topped up litter and hit reset—**how long** until we need to do that again?”  
- “The box said full at breakfast—**how long** did it sit before someone emptied it?”  
- “Are we getting better or worse at responding to full bags?”  

Those answers reduce smell, overflow, and household friction. They are first-class product, not diagnostics noise.

### 1.3 Design principles (non-negotiable)

| Principle | Meaning for implementers |
|-----------|--------------------------|
| **Honest empty states** | Prefer **None**, **Unknown**, **Unavailable**, **Never**, **Not enough data** over invented zeros or averages of empty sets. |
| **No fake identity** | No pet name without API (or explicit user mapping). Guest/weight-only → **Unknown**. |
| **Local history unless proven otherwise** | Day/7d/30d and “time between X” live in an append-only event store. |
| **Per-box chores; account-scoped pets** | Bag/litter/full metrics are per `iotid`. Pet visit metrics span all boxes under one config entry. |
| **Cat-lover language** | Entity names and states read like a pet parent dashboard, not a raw telemetry dump. |
| **Lean Gold** | High-value sensors first; avoid entity explosion; optional/diagnostic where noisy. |
| **Useful API → visible in HA** | Every BA-useful **read** and **read/write** cloud field gets a first-class HA surface (entity preferred; attribute only when HA practice says so). No “API knows it but HA can’t automate on it.” |
| **HA-native platforms** | Map data to the **correct platform** (binary_sensor, sensor, switch, button, select, number, …)—not generic text dumps. |
| **Performance-first exposure** | Expose useful fields **without** extra cloud round-trips when data is already in the poll payload; never add poll frequency just to decorate diagnostics. |

---

## 2. Domain glossary (use these terms in code, docs, and UI)

| Term | Meaning | Code / signal notes (1.2.x) |
|------|---------|------------------------------|
| **Box / litter box** | One Furbulous device | `iotid` / device id |
| **Pet / cat** | One animal on the account pet roster | `pet/list` (≤1 min cadence + full poll) |
| **Empty / dash** | Visit or metric not linked / no data yet | UI **`-`** for text; numeric classes use empty/`None` |
| **Visit** | One occupancy cycle: enter → leave | `workstatus` Working(1) → Idle |
| **Pack** | Waste bag sealed/packed | Button → `handMode: 3` |
| **Empty / dump** | Waste emptied / bag taken out (product sense TBD) | Button → `handMode: 2` (“dump” in code) |
| **Bag in use** | Current waste liner is the active bag | Implicit between bag-cycle milestones |
| **Bag replaced** | New bag fitted; previous bag cycle closed | Event `bag_replaced` — **definition §5.1** |
| **Bag lifetime** | Time a single bag was in use | `bag_ended.ts − bag_started.ts` |
| **Litter top-up** | User physically added litter | Often unobserved by cloud; may only see **reset** |
| **Litter reset** | User pressed **reset** after adding litter (sensor/level baseline) | **API TBD**; helper button fallback |
| **Litter interval** | Time between consecutive litter resets | Primary “how long does litter last?” proxy |
| **Waste full** | Box reports full waste | `errorReportEvent` bit **16 or 32** (“Litter full”) → binary **Needs emptying** |
| **Full episode** | Continuous period while waste full is true | One open episode at a time per box |
| **Time-to-clear / time-to-take-out** | How long the full bag sat before cleared | `waste_full_off.ts − waste_full_on.ts` |
| **Cleared** | Full condition ends (bag taken out / emptied / pack cycle completed) | Full true→false; ideally after Empty/Pack |

---

## 3. Data architecture (required reading)

### 3.1 What the cloud client already gives us (proven in this repo)

| Source | Content | Time horizon |
|--------|---------|--------------|
| Device list | Box identity, name, online, last activity | Live |
| Properties get | Live state: occupancy, weight, errors, modes, handMode, … | Live snapshot |
| wcheader | `times`, `avg_duration`, day-over-day diffs | **Today only**, **per box** |
| Property set | Commands: clean/empty/pack/delay/locks | Instant actions |
| DND API | Sleep/DND | Live |
| **pet/list**, **pet/info** | Pet roster (fields not fully documented in-repo) | Live roster |

### 3.2 What we do **not** have proven

- Server-side **visit history**, **pack/empty history**, **litter reset history**, **bag replacement history**  
- Native **7-day / 30-day** aggregates  
- Proven property for **“current pet in box”** or **“Unknown”** label  
- Proven API for **litter reset** button  
- Proven mapping of Pack vs Empty vs “bag replaced” in the official app UX  

### 3.3 Two layers

| Layer | Role |
|-------|------|
| **A. Cloud live + roster** | Poll pets; poll box state; show live “in box”, weight, full, commands |
| **B. Local analytics store** | Append-only **events** from poll deltas + successful HA commands; roll up day/7d/30d |

```text
Cloud poll / button success
        │
        ▼
  Edge detectors (occupancy, full, commands, reset)
        │
        ▼
  Append event (UTC ts, device_id, type, payload)
        │
        ▼
  Rollup engine → HA sensors (today / 7d / 30d / last / avg)
```

**Rules:**

1. If a metric says “last month / average between X,” it is **Layer B** unless discovery finds history.  
2. Never invent pet identity. Missing → **Unknown**.  
3. Never invent chore history. Zero events → **None** / **Never**, not `0` averages.  
4. Prefer **presence coordinator (~30s)** for occupancy and full-edge detection; chore commands can also emit on HA button success.  
5. **API visibility:** If Layer A already returns a field (or a cheap authenticated call returns it) and BA marks it useful → **expose it in HA** per §3A. Analytics (Layer B) does not replace live API exposure.

---

## 3A. API surface visibility (cat-lover BA + HA best practices)

### 3A.1 Product rule (non-negotiable)

> **All read and read/write data elements from the Furbulous API that the cat-lover business analyst judges helpful for home automation or cat-care UX must be visible and usable from the Home Assistant integration.**

| Access | Meaning in HA |
|--------|----------------|
| **Read** | User can **see** current state on a device/entity and use it in automations, templates, dashboards, Assist, and voice |
| **Read/write** | User can **see state and change it** from HA (switch/select/number/button as appropriate)—not only from the vendor app |

**Out of scope for “must expose as entity”:**

- Auth secrets, tokens, passwords  
- Internal opaque IDs that only enable other calls (keep in diagnostics redacted form if needed)  
- Fields with **no** cat-care or automation value after BA review (document as **BA-skip** with reason)  
- Invented fields not present in the API  

**In scope even if “technical”:** firmware version, product name, completion status, day-over-day stats diffs, litter type (if present), etc.—if a cat lover or home automator would use them for alerts, dashboards, or scripts.

### 3A.2 BA value test (use before adding or rejecting an entity)

Expose when **any** of the following is true:

1. **Automation trigger/condition** — e.g. full, occupied, online, error, DND, child lock  
2. **Cat health or behavior** — weight, visits, duration, who is in the box  
3. **Household chore** — empty/pack, bag/litter cycles, time-to-clear  
4. **Safety / device care** — drawer open, cover open, motor errors, offline  
5. **Convenience control** — auto mode, clean delay, clean/pause/resume, sleep/DND  
6. **Multi-device identity** — box name, product, firmware (support + “which box is which”)  
7. **Trend / day stats already paid for in the poll** — wcheader fields already fetched should not stay hidden  

Skip or demote only when:

- Pure vendor-internal (no user meaning after discovery)  
- Duplicate of another entity with the same semantic (expose once, map cleanly)  
- High-churn raw value better as **attribute** of a parent entity (HA practice)

### 3A.3 Home Assistant best practices (entity design)

Align with [HA Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) and this integration’s Gold-lean path:

| Practice | Guidance for Furbulous |
|----------|------------------------|
| **Correct platform** | Boolean state → `binary_sensor` or `switch` (if user-toggleable). Continuous measurement → `sensor` + device class. Discrete modes → `select`. Momentary actions → `button`. Never model a toggle as a button-only if the API has readable state. |
| **`has_entity_name` + translations** | Friendly names via `translation_key` / `strings.json`; device name provides context (“Living Room Box · Cat weight”). |
| **Device class & units** | Weight → `WEIGHT` + native g + suggested mass unit; duration → `DURATION` + seconds; connectivity → `CONNECTIVITY`; timestamps → `TIMESTAMP`. |
| **State class** | `MEASUREMENT` for live gauges; `TOTAL_INCREASING` only when truly monotonic (careful with daily counters that reset). |
| **Entity category** | Primary UX = no category. Setup knobs → `config`. Support/debug → `diagnostic`. Do **not** hide primary cat-care signals as diagnostic. |
| **Enabled by default** | High-value cat/automation entities **on**. Noisy, secondary, or rare-use entities **disabled by default** (user can enable)—keeps first-run UX clean. |
| **Stable `unique_id`** | Never change; include device + semantic key. |
| **Unavailable vs unknown** | Coordinator failure / offline device → `unavailable` when appropriate; missing optional field → `unknown` or entity not created if property absent. |
| **Parallel updates** | Platform `PARALLEL_UPDATES = 0` when coordinator owns refresh (already). |
| **Actions raise translated errors** | Failed set_property → `HomeAssistantError` with translation key. |
| **No entity explosion** | Prefer one well-named sensor over five near-duplicates; put secondary detail in **attributes** when HA users would not automate on them alone. |
| **Registry-friendly** | Respect unit overrides; reconfigure/reauth clears sticky display issues (as 1.2.x weight path). |

### 3A.4 Performance, responsiveness, and “user happy” code

Exposing more fields must **not** make the integration feel slow or fragile.

| Rule | Why |
|------|-----|
| **Zero extra HTTP for fields already in `properties/get`** | Vendor returns the full property map in one call. Mapping another key to a sensor is O(1) local work—**always prefer this over new endpoints**. |
| **Keep dual poll model** | Full ~5 min (list + properties + daily stats [+ pets when entities need them]); presence ~30s (properties only). Do not poll pets or wcheader on the 30s path. |
| **Poll pets only when pet entities exist** | When P1 ships, add `pet/list` to the **full** snapshot (or slower pet-only interval), not presence. |
| **Push-on-command** | After successful write (switch/button/select), `async_request_refresh` (or optimistic local state + short refresh)—user sees change quickly. |
| **Entity `extra_state_attributes` sparingly** | Attributes update with state; avoid huge blobs. Diagnostics is for bulk key dumps. |
| **Fingerprint / partial updates** | Keep efficient availability and write-when-changed patterns so 30s occupancy does not thrash the state machine. |
| **No unbounded history in coordinator data** | Layer B store is separate; coordinator holds **current snapshot only**. |
| **Pi-friendly** | Cap analytics retention; avoid N+1 APIs; shared `aiohttp` session (already). |
| **Honest latency** | Cloud polling is not local push. Document intervals; don’t promise sub-second occupancy. |
| **Disabled-by-default for low-value noise** | Users who want “everything” can enable; default dashboard stays calm. |

### 3A.5 Known API inventory → HA visibility (BA matrix)

Status key: **Done** = in 1.2.x · **Gap** = API known / partially known but not (fully) visible · **Discover** = needs capture · **Layer B** = local analytics (not pure API)

#### Device list / account (read)

| API element | Access | BA value (cat / automation) | HA surface | Enable default | Status |
|-------------|--------|-----------------------------|------------|----------------|--------|
| Device `name` | R | Identify box | Device registry name | on | Done |
| `device_online` | R | Offline alerts | Binary sensor **Connected** (diagnostic) | on | Done |
| `active_time` | R | Stale device / last seen | Sensor **Last activity** (diagnostic, timestamp) | on | Done |
| `product_name` | R | Support, multi-model | DeviceInfo `model` / diagnostic sensor | on | Gap if not in DeviceInfo fully |
| `version` (firmware) | R | Update / support automations | Diagnostic sensor **Firmware** | on (diagnostic) | Gap |
| `iotid` / `id` | R | Internal | Diagnostics only (redacted) | — | Done (diagnostics) |
| `is_disturb` (list) | R | DND state | Prefer properties/DND switch state | on | Partial via DND switch |

#### Properties map (read; one HTTP already)

| API element | Access | BA value | HA surface | Enable default | Status |
|-------------|--------|----------|------------|----------------|--------|
| `workstatus` (cat present) | R | Automations (light, camera, notify) | Binary **Cat in litter box** | on | Done |
| `catWeight` | R | Health, identity assist | Sensor **Cat weight** (WEIGHT) | on | Done |
| `errorReportEvent` | R | Safety + full bag | Sensor **Error** (diagnostic) + derived binaries | on | Done (error); full binary Done |
| Waste full (code 16) | R | Chore automations | Binary **Waste bin full** | on | Done |
| Drawer not in place (64) | R | Safety | **Not in cloud** (live drawer-out=0). 64 only with 524288 = trash-door E4 | on | **Falsified** |
| Cover open (128) | R | Safety | Binary **Cover open** | on | Gap |
| Motor / sensor errors (1,2,4,8,…) | R | Maintenance | Keep on Error sensor; optional problem binaries | diagnostic | Partial (text error only) |
| `FullAutoModeSwitch` | R/W | Control cleaning behavior | Switch **Full auto mode** | on | Done |
| `childLockOnOff` | R/W | Safety for kids/pets curious paws | Switch **Child lock** (+ diagnostic binary OK) | on | Done |
| `masterSleepOnOff` | R | Sleep/quiet | Binary **Sleep mode** (diagnostic); write if API allows | on | Partial (read binary; write?) |
| `catCleanOnOff` (delay minutes) | R/W | Timing after visit | Select **Cleaning delay** | on (config) | Done |
| `handMode` | R/W | Clean / empty / pack / pause / resume | Buttons for actions; optional diagnostic **Current hand mode** | buttons on; mode sensor diagnostic | Partial (buttons only) |
| `completionStatus` | R | Cycle finished automations | Sensor **Completion status** (enum/text) | diagnostic or on | Gap |
| `excreteTimesEveryday` | R | Visits today (device-side) | Sensor if distinct from wcheader; else attribute | disable if duplicate | Gap / validate vs wcheader |
| `excreteTimerEveryday` | R | Duration stats | Same as above | disable if duplicate | Gap / validate |
| Current pet / name during visit | R | Multi-cat | Sensor **Occupying pet** | on | Discover |
| Litter type / level / reset | R or R/W | Chores | Sensors + button/select as discovered | on | Discover |
| Any new property post-discovery | R/W | Apply BA value test | Proper platform | per §3A.2 | Ongoing |

#### Daily stats `wcheader` (read; already on full poll)

| API element | Access | BA value | HA surface | Enable default | Status |
|-------------|--------|----------|------------|----------------|--------|
| `times` | R | Visits today | Sensor **Daily uses** | on | Done |
| `avg_duration` | R | Session length today | Sensor **Average daily duration** | on | Done |
| `times_diff` | R | Day-over-day change (delight + anomaly) | Sensor **Uses vs yesterday** or attribute on Daily uses | disable-by-default or attribute | Gap |
| `avg_diff` | R | Duration trend | Attribute or secondary sensor | disable-by-default | Gap |

#### Commands / write endpoints (read/write)

| API element | Access | BA value | HA surface | Enable default | Status |
|-------------|--------|----------|------------|----------------|--------|
| `properties/set` FullAutoModeSwitch | R/W | Control | Switch | on | Done |
| `properties/set` childLockOnOff | R/W | Safety | Switch | on | Done |
| `properties/set` catCleanOnOff | R/W | Delay | Select | on | Done |
| `properties/set` handMode 1 clean | W (momentary) | Manual clean | Button | on | Done |
| `properties/set` handMode 2 empty | W | Take out waste | Button | on | Done |
| `properties/set` handMode 3 pack | W | Seal bag | Button | on | Done |
| `properties/set` handMode 4 pause | W | Pause cycle | Button | on | Done |
| `properties/set` handMode 5 resume | W | Resume | Button | on | Done |
| `device/disturb` DND | R/W | Quiet hours | Switch **Do not disturb** | on | Done |
| Litter reset (TBD) | W or R/W | Litter analytics + chore | Button (+ state if readable) | on | Discover / helper |
| Sleep mode write (if API) | R/W | Night mode from HA | Switch if writable | on | Discover |
| Any other settable property | R/W | If BA-useful | Correct platform with **readable state** when API provides it | per test | Ongoing |

#### Pets (read; not polled in 1.2.x)

| API element | Access | BA value | HA surface | Enable default | Status |
|-------------|--------|----------|------------|----------------|--------|
| `pet/list` names/ids | R | Multi-cat household | Pet devices + name | on | Gap (API exists, not polled) |
| `pet/info` / weight fields | R | Health | Per-pet sensors | on | Discover fields |
| Pet photo URL | R | Delight | Entity picture if stable | optional | Discover |

#### Layer B (local) — still “visible in HA” once implemented

All bag lifetime, time-to-clear, litter interval, 7d/30d visit, favorite box metrics in §5–7 must ship as **entities**, not only logs—same visibility rule.

### 3A.6 Mapping rules (how to expose, not only whether)

```text
API field
  → BA value test (§3A.2)
  → If fail: document BA-skip + reason in this matrix
  → If pass:
       → Already in poll payload? map entity (no new HTTP)
       → Needs new endpoint? add to full poll only if entities consume it
       → Choose platform (R vs R/W)
       → category + default enabled
       → device_class / unit / translation
       → tests + README “supported functions”
```

**Read/write consistency:** If the user can change a value in the app and the API exposes both get and set, HA must expose **state + control**, not a write-only button when a switch/select is correct.

**Duplicate semantics:** One user-facing concept → one primary entity. Example: waste full is a **binary_sensor** for automations; the general **Error** sensor may still show the text “Litter full…”.

**Attributes vs entities:** Use attributes when values are explanatory (e.g. `sample_count` on an average, `times_diff` on daily uses). Promote to entity when users will trigger automations or put it on a dashboard badge.

### 3A.7 Gaps to close for “API useful ⇒ visible” (vs 1.2.x)

Priority for implementers (cat-lover order, still performance-safe):

| Pri | Gap | Why cat lovers / HA users care | Cost |
|-----|-----|--------------------------------|------|
| P0 | Pet roster visible | Names, multi-cat | +1 call on full poll when entities exist |
| P0 | Occupying pet (when discovered) | Automations per cat | Map property only |
| P1 | Cover open / drawer / rich problem binaries | Safety, “why is it stuck?” | Map error bits; no new HTTP |
| P1 | `completionStatus` | “Cycle finished” automations | Map property |
| P1 | `handMode` current value (diagnostic) | See what box is doing | Map property |
| P1 | wcheader `times_diff` / `avg_diff` | Today vs yesterday at a glance | Map fields already fetched |
| P1 | Firmware / model diagnostic sensors | Support, multi-box | Device list fields already fetched |
| P2 | Sleep write if API supports | Full parity with app | Discovery |
| P2 | Litter reset control + state | Chore + analytics | Discovery or helper |
| P2–P6 | Layer B analytics entities | Bag/litter/full timing | Local store |

### 3A.8 What “visible in the integration” means in the HA app

Users should find BA-useful data without YAML:

1. **Settings → Devices & services → Furbulous → device** — entities listed with clear names  
2. **Automations UI** — entities selectable as triggers/conditions/actions  
3. **Dashboards** — card-friendly device classes and units  
4. **Voice / Assist** — sensible names (“turn on child lock on Living Room Box”)  
5. **Diagnostics download** — remaining raw keys for support; **not** a substitute for entities  

If a field is only in diagnostics JSON, it is **not** yet “visible” for home automation.

---

## 3B. Performance budget (when expanding visibility)

| Budget item | Target |
|-------------|--------|
| Full poll interval | ~5 minutes (unchanged default) |
| Presence poll interval | ~30 seconds (occupancy-critical only) |
| Extra endpoints on presence path | **None** |
| New full-poll endpoints | Only if ≥1 default-enabled entity needs them (e.g. pets) |
| Coordinator payload | Current snapshot only; no history arrays |
| Entity count per box (default enabled) | Prefer **&lt; ~25** primary; rest diagnostic or disabled-by-default |
| Analytics write | O(1) append; prune ≤ daily |
| UI responsiveness after button/switch | Refresh or optimistic update within one command RTT |

If a proposed entity would force faster cloud polling or large history pulls, **reject or redesign** (local Layer B, attributes, or disabled-by-default + slower poll).

---

## 4. Event catalog (developer contract)

Store events with **UTC** timestamps. Default prune older than **90 days** (configurable later). One record per event. Include `config_entry_id` + `device_id` / `iotid`.

### 4.1 Event types

| `event_type` | When to emit | Required fields | Optional / notes |
|--------------|--------------|-----------------|------------------|
| `visit_started` | Occupancy false→true | `device_id`, `iotid`, `ts` | `weight_g`, identity fields |
| `visit_ended` | Occupancy true→false | `device_id`, `iotid`, `ts`, `duration_s`, `visit_id` | identity; weight at end |
| `weight_sample` | Meaningful weight change | `device_id`, `ts`, `weight_g` | identity |
| `waste_full_on` | Full false→true (debounced) | `device_id`, `ts`, `episode_id` | raw `errorReportEvent` |
| `waste_full_off` | Full true→false | `device_id`, `ts`, `episode_id`, `time_full_s` | `cleared_how` |
| `pack` | Successful Pack **or** inferred pack complete | `device_id`, `ts`, `source` | `source`: `ha_button` \| `app_inferred` \| `device_inferred` |
| `empty` | Successful Empty **or** inferred | `device_id`, `ts`, `source` | same |
| `bag_replaced` | Bag cycle closed per §5.1 | `device_id`, `ts`, `source`, `lifetime_s` | `hours_since_previous_bag`, `visits_during_bag`, `packs_during_bag` |
| `litter_reset` | Reset confirmed | `device_id`, `ts`, `source` | `interval_s` since previous reset |
| `litter_added` | Optional explicit top-up | `device_id`, `ts`, `source` | Only if distinguishable from reset |

### 4.2 Identity fields (visit-related)

| Field | Values |
|-------|--------|
| `pet_id` | API id or `null` |
| `pet_name` | API name or `"Unknown"` (display via i18n) |
| `identity_confidence` | `high` \| `low` \| `none` (optional v2) |
| `identity_source` | `api_current_pet` \| `weight_match` \| `none` |

### 4.3 Occupancy edge detection

- Use **presence coordinator** (~30s).  
- Debounce flaps shorter than **N seconds** (default **20s**, decision D5) — do not count as visits.  
- One completed visit → one `visit_ended` with `duration_s`.

### 4.4 Storage shape (suggested)

```json
{
  "event_id": "uuid",
  "event_type": "bag_replaced",
  "ts": "2026-08-10T18:22:00Z",
  "config_entry_id": "...",
  "device_id": "...",
  "iotid": "...",
  "source": "ha_button",
  "payload": {
    "lifetime_s": 345600,
    "visits_during_bag": 52,
    "packs_during_bag": 3
  }
}
```

Implementation may use SQLite, HA Store, or a small JSON-backed store; choose something durable across restarts and cheap on Pi.

---

## 5. Maintenance cycles — bags, litter, full-bag response

These are **chore analytics**. Treat them as carefully as visit metrics. This section is the detailed contract for the three areas you called out: **bag lifetime**, **litter + reset intervals**, and **time-to-take-out after full**.

---

### 5.1 Waste bag lifecycle (“how long do bags last?”)

#### 5.1.1 Cat-lover journey

```text
[New bag fitted]
      │
      │  cats visit; waste accumulates; optional intermediate packs
      ▼
[Bag still in use] ──► Waste full (error 16) ──► user packs / empties / removes bag
      │
      ▼
[Bag replaced / new bag fitted] ──► emit bag_replaced ──► new cycle starts
```

Real multi-cat homes often:

- Pack more than once before fully replacing a liner (depends on model/habit).  
- Leave a full bag for hours if nobody is home.  
- Change bags from the **app, device, or HA**—so HA button-only tracking is incomplete without inference.

#### 5.1.2 Product questions (resolve in discovery — do not hardcode forever)

| ID | Question | Why it matters |
|----|----------|----------------|
| Q-B1 | Is **Pack** = seal only, and **Empty** = remove bag / drawer dump? | Closes bag cycle definition |
| Q-B2 | Does the app have a separate “bag replaced” or only Pack/Empty? | Event source |
| Q-B3 | Can Pack/Empty happen **only** on-device without HA seeing a button? | Requires property inference |
| Q-B4 | Can a bag be replaced **without** a prior full event? | Yes—users preemptively change bags |
| Q-B5 | Can full clear without Empty/Pack? | Manual drawer / unknown clear |

#### 5.1.3 Recommended default definition (until discovery overrides)

| Milestone | Analytics definition |
|-----------|----------------------|
| **Bag started** | Timestamp of previous `bag_replaced`, **or** first reliable observation after install (cold start — **do not** count cold start as a completed lifetime until a second replacement closes a real cycle) |
| **Bag ended / replaced** | Configurable `bag_cycle_closes_on`: **`empty` (default)** \| `pack` \| `either` \| `full_clear_after_empty_or_pack` |
| **Completed bag lifetime** | Only when we have **two** consecutive bag-close milestones: `lifetime = bag_replaced_n.ts − bag_replaced_(n-1).ts` |
| **In-progress bag age** | `now − last bag_replaced` (or `now − install_observation` with attribute `provisional=true`) |

**Default close rule (D1):** Prefer **Empty** (`handMode: 2`) as “bag taken out / cycle closed,” because vendor error copy is *“Litter full - Need to empty”* and the Empty button is labeled dump/empty. Allow option to close on Pack if field data shows users only Pack.

**Inference when user acts outside HA:**

1. Prefer explicit successful HA `empty` / `pack` events.  
2. Else if **waste full** goes true→false **and** nearby property/mode changes suggest dump/pack → emit `empty`/`pack` with `source=*_inferred` and close bag per config.  
3. Else if full clears with no command signal → `waste_full_off` with `cleared_how=unknown`; **do not** auto-close bag cycle unless config says full-clear closes bag.

#### 5.1.4 Bag metrics (per box)

| Metric ID | Friendly name | Formula | Empty / cold state |
|-----------|---------------|---------|-------------------|
| `bag.last_replaced_at` | Last bag replaced | `ts` of latest `bag_replaced` | **Never** |
| `bag.hours_since_replaced` | Hours since bag replaced | `now − last_replaced` | **Never** if no event |
| `bag.last_lifetime_hours` | Last bag lifetime | Lifetime of most recently **completed** cycle (needs ≥2 replacements) | **None** if &lt;2 closes |
| `bag.avg_lifetime_hours_30d` | Avg bag lifetime (30d) | Mean of completed lifetimes whose **end** falls in rolling 30d | **None in last 30 days** if n=0 |
| `bag.min_lifetime_hours_30d` | Shortest bag (30d) | Min of those lifetimes | **None** |
| `bag.max_lifetime_hours_30d` | Longest bag (30d) | Max | **None** |
| `bag.count_replaced_30d` | Bags replaced (30d) | Count of `bag_replaced` in 30d | `0` is OK for counts; avgs still **None** if 0 completed pairs |
| `bag.visits_during_last_bag` | Visits on last bag | Count `visit_ended` between previous and last replace | **None** if incomplete |
| `bag.avg_visits_per_bag_30d` | Avg visits per bag (30d) | Mean visits over completed cycles in window | **None** |

**Display guidance:** Prefer **days + hours** in Lovelace examples (`4.2 days`) while storing **seconds** natively (`SensorDeviceClass.DURATION`).

#### 5.1.5 State machine (bag cycle)

```text
                 install / first seen
                        │
                        ▼
              ┌───────────────────┐
              │  BAG_IN_USE       │◄──────────────────────────┐
              │  (open cycle)     │                           │
              └─────────┬─────────┘                           │
                        │ close_event (Empty default)           │
                        ▼                                       │
              emit bag_replaced                                 │
              compute lifetime vs previous close ───────────────┘
```

**Rules:**

- At most one open bag cycle per box.  
- First close after install: emit `bag_replaced` for “we know a bag change happened,” but **last/avg lifetime** stay **None** until a **second** close provides a duration.  
- Attribute `completed_cycles_count` on diagnostics helps debug.

#### 5.1.6 Edge cases (bags)

| Case | Expected behavior |
|------|-------------------|
| User empties twice quickly | Debounce (e.g. second empty within **5 min** of bag_replaced does not start a zero-length lifetime) |
| Pack without Empty | Count `pack`; do **not** close bag unless config closes on pack |
| Empty without prior full | Still valid preemptive bag change → close cycle |
| Integration offline during bag change | May miss event; next successful empty after reconnect closes with possible **inflated** lifetime — attribute `gap_risk=true` if offline &gt; threshold during cycle |
| Multi-box | Metrics never merge bags across devices |

#### 5.1.7 Cat-lover automations (examples, not required code)

- Notify when `hours_since_replaced` &gt; 1.2 × `avg_lifetime_hours_30d` (overdue bag).  
- Dashboard: “Last bag lasted **5.1 days** · Avg **4.4 days** · Current bag **3.2 days** old.”

---

### 5.2 Time-to-take-out after full (“how long did the full bag sit?”)

This is **response-time analytics**, separate from bag lifetime. A bag can last 5 days total while the last full episode only sat 45 minutes.

#### 5.2.1 Cat-lover journey

```text
Waste not full ──► error 16 / Waste bin full ON ──► [waiting / smell risk]
                              │
                              │  user empties / packs / removes bag
                              ▼
                    Waste full OFF ──► time_to_clear = off − on
```

Questions cat lovers ask:

- “How long did it sit **last** time?”  
- “On average, how long do we leave a full bag?”  
- “What’s the **worst** delay this month?”  
- “It’s full **right now**—how long has it been?”

#### 5.2.2 Definitions

| Term | Definition |
|------|------------|
| **Full episode start** | Debounced transition to waste full true (`errorReportEvent == 16` today) |
| **Full episode end** | Transition to waste full false |
| **Time-to-clear (episode)** | `end_ts − start_ts` |
| **Still full (live)** | If currently full: `now − start_ts` (“waiting time”) |
| **Cleared how** | `empty` \| `pack` \| `unknown` \| `other` |

#### 5.2.3 Debounce & integrity

| Rule | Default |
|------|---------|
| Full must be true for **≥2 consecutive presence polls** before `waste_full_on` | D6 |
| One open episode per box | Ignore duplicate full-true while open |
| Full blip true→false→true within **2 min** | Merge into same episode (optional v1.1) |
| Integration restart while full | Restore open episode from last `waste_full_on` if full still true; else close with `cleared_how=unknown` and `gap_risk=true` |

#### 5.2.4 Metrics (per box)

| Metric ID | Friendly name | Formula | Empty state |
|-----------|---------------|---------|-------------|
| `full.is_full` | Waste bin full | Live binary (exists 1.2.x) | — |
| `full.current_waiting_s` | Time full (current) | If full: `now − episode_start`; else `0` | `0` when not full |
| `full.last_time_to_clear_s` | Last time-to-clear | Most recent completed episode duration | **None** if never completed |
| `full.avg_time_to_clear_s_30d` | Avg time-to-clear (30d) | Mean of completed episodes ending in 30d | **None in last 30 days** |
| `full.median_time_to_clear_s_30d` | Median time-to-clear (30d) | Median (optional P1; less skewed by one long vacation) | **None** |
| `full.max_time_to_clear_s_30d` | Max time-to-clear (30d) | Worst case (“shame metric” / SLA) | **None** |
| `full.min_time_to_clear_s_30d` | Fastest clear (30d) | Min | **None** |
| `full.episodes_30d` | Full episodes (30d) | Count completed in window | `0` OK |
| `full.last_full_at` | Last became full | `ts` of last `waste_full_on` | **Never** |
| `full.last_cleared_at` | Last cleared | `ts` of last `waste_full_off` | **Never** |

#### 5.2.5 Relationship to bag replace

| Scenario | Events |
|----------|--------|
| Full → Empty → bag out | `waste_full_on` → `empty` → `waste_full_off` → `bag_replaced` (if Empty closes bag) |
| Full → Pack only | `pack`; full may or may not clear — observe properties; bag may stay open |
| Empty without full | No full episode; bag may still replace |

Do **not** equate bag lifetime with time-to-clear. They answer different questions.

#### 5.2.6 Edge cases (full)

| Case | Behavior |
|------|----------|
| Full clears without Empty/Pack | Still complete episode; `cleared_how=unknown` |
| Full never clears before next full | Impossible if one open episode; keep single open |
| User away 3 days | Large time-to-clear is **valid data**—include in avg; surface **max** so outliers are visible |
| Error code multi-bit | Treat bit/value **16** consistently with existing binary sensor |

#### 5.2.7 Automations (examples)

- Notify at full + escalate if `current_waiting` &gt; 2h / 6h.  
- Weekly summary: “Avg full-bag wait: **48 min** (max **5.2 h**).”

---

### 5.3 Litter top-up + reset button (“how long between litter adds/resets?”)

#### 5.3.1 Cat-lover journey

```text
[Fresh litter baseline after reset]
        │
        │  visits, clumping, evaporation, tracking
        ▼
[Litter low / dirty / owner judgment]
        │
        │  add litter (physical)
        ▼
[Press Reset in app/device/HA] ──► litter_reset event ──► interval = now − previous reset
```

**Important product insight:** Most smart boxes do **not** reliably detect “I poured litter.” What they (and we) can measure well is **time between resets**—the owner’s deliberate “fresh baseline” signal. That is the right proxy for “how long does a litter fill last in *this* household?”

#### 5.3.2 Two optional event models

| Model | When to use | Events |
|-------|-------------|--------|
| **A. Reset-only (recommended v1)** | Only reset is observable | `litter_reset` only; interval = gap between resets |
| **B. Add + reset** | If discovery shows separate “added litter” vs reset | `litter_added` then `litter_reset`; track **time from add→reset** *and* **reset→reset** |

**User’s request mapped:**

| Ask | Metric |
|-----|--------|
| How long between adding litter and needing to press reset | If only reset known: treat reset as the completed chore and report **reset→reset** (document limitation). If add+reset known: `litter_reset.ts − litter_added.ts` for last/avg **chore lag**, plus reset→reset for **fill longevity**. |
| Last & averages | `last_interval`, `avg_interval_30d`, plus live `hours_since_last_reset` |

#### 5.3.3 API gap & fallbacks

| Source | Status |
|--------|--------|
| Vendor litter-reset property/endpoint | **Not proven** in this repo — discovery required |
| HA helper button “I reset litter” | **Allowed fallback (D7)** — still produces excellent analytics |
| App-only reset | Needs capture; then map to same `litter_reset` event |

**Until source exists:** expose entities as **Unavailable** with reason `litter_reset_source_unknown`, **or** ship helper button so analytics work day one.

#### 5.3.4 Metrics (per box)

| Metric ID | Friendly name | Formula | Empty state |
|-----------|---------------|---------|-------------|
| `litter.last_reset_at` | Last litter reset | Latest `litter_reset` ts | **Never** |
| `litter.hours_since_reset` | Hours since litter reset | `now − last_reset` | **Never** |
| `litter.last_interval_hours` | Last interval between resets | Gap between last two resets | **None** if &lt;2 resets |
| `litter.avg_interval_hours_30d` | Avg interval between resets (30d) | Mean of gaps whose **later** reset is in 30d | **None in last 30 days** |
| `litter.min/max_interval_hours_30d` | Min/max interval (30d) | Extremes | **None** |
| `litter.resets_30d` | Resets (30d) | Count | `0` OK |
| `litter.last_add_to_reset_hours` | Last add→reset lag (model B) | Last pair | **None** / **Unavailable** if model A |
| `litter.avg_add_to_reset_hours_30d` | Avg add→reset lag (model B) | Mean | **None** |

#### 5.3.5 Edge cases (litter)

| Case | Behavior |
|------|----------|
| Double-tap reset | Debounce **10 min**: second reset does not create a near-zero interval |
| First reset ever | Emit event; intervals stay **None** until second |
| Reset without adding litter | Still count (owner signal); product cannot force honesty |
| Different litter brands | Out of scope for v1; optional note attribute later |
| Multi-box | Per box always |

#### 5.3.6 Automations (examples)

- Remind if `hours_since_reset` &gt; 1.15 × `avg_interval_hours_30d`.  
- Card: “Litter last reset **6 days ago** · You usually last **9 days**.”

---

### 5.4 Pack frequency (related chore, from original list)

| Metric ID | Friendly name | Formula | Empty |
|-----------|---------------|---------|-------|
| `pack.last_at` | Last pack | Latest `pack` ts | **Never** |
| `pack.hours_since` | Hours since last pack | `now − last` | **Never** |
| `pack.avg_hours_between_30d` | Avg hours between packs (30d) | Mean gaps | **None in last 30 days** |
| `pack.count_30d` | Packs (30d) | Count | `0` OK |
| `pack.visits_since_last` | Visits since last pack | Count visit_ended after last pack | Cat-lover gold |

Correlate: “Bag held **47 visits** before pack.”

---

### 5.5 Cross-chore dashboard (product mock for developers)

Suggested Lovelace mental model (not required YAML):

```text
┌─ Box: Upstairs ─────────────────────────────────────────┐
│ Waste: FULL · waiting 1h 12m                            │
│ Last full wait: 42m · Avg (30d): 58m · Max: 4.1h        │
│ Bag: 3.2 days old · Last bag lasted 5.1d · Avg 4.6d     │
│ Litter: reset 6d ago · Last interval 9d · Avg 8.4d      │
│ Packs (30d): 11 · Visits since pack: 14                 │
└─────────────────────────────────────────────────────────┘
```

This is the “awesome for cat lovers” bar for chore analytics.

---

## 6. Pet & visit analytics (methodical full list)

### 6.1 Capability matrix

| # | Capability | Cat-lover why | Priority | Layer | Window | Notes |
|---|------------|---------------|----------|-------|--------|-------|
| V1 | Pet roster with **names** | “Who lives here?” | P0 | A | live | `pet/list` |
| V2 | Display **Unknown** when no name/id | Guests, failures, honesty | P0 | A/B | live | Never invent |
| V3 | Pet weight (if API) | Health trend | P0 | A | live | Fields TBD |
| V4 | Box occupied | Is someone in there? | **Done** | A | live | `workstatus` |
| V5 | **Occupying pet** name or Unknown | Multi-cat peace of mind | P0 | A (+B) | live | Discovery blocker |
| V6 | Cat weight on box | Weight after visit | **Done** | A | live | g + suggested lb |
| V7 | Last visitor name/Unknown | Who was just here? | P1 | B | live | After visit_ended |
| V8 | Box visits today | Daily activity | P0 | A/B | 1d | wcheader +/or events |
| V9 | Box visits 7d / 30d | Trends | P0 | B | 7d/30d | Local only |
| V10 | Box avg duration today | Session length | P0 | A | 1d | wcheader |
| V11 | Box avg duration 7d/30d | Trends | P1 | B | 7d/30d | |
| V12 | **Per-cat** visits 1d/7d/30d | Fairness / health | P0 | B | | Needs identity or Unknown bucket |
| V13 | **Per-cat** avg duration 1d/7d/30d | Behavior change | P0 | B | | “Past month” = 30d rolling |
| V14 | Favorite litter box per cat | Multi-box homes | P0 | B | 30d | Max visits; ties → most recent |
| V15 | Favorite share % | How dominant | P1 | B | 30d | |
| V16 | Insufficient data for favorite | Avoid nonsense | P0 | B | | &lt;3 visits → **Not enough data** |
| V17 | Unknown visit counts | Still count on box totals | P0 | B | | Separate “Unknown” pseudo-pet optional |
| V18 | Weight history per cat | Health | P2 | B | 30d | Only if identifiable samples |
| V19 | Pet photo / rich profile | Delight | P2 | A | | If API has it |
| V20 | HA device per pet | Navigation | P1 | A | | `pet_{id}` |

### 6.2 Visit rules

- Debounce **20s** flaps (D5).  
- Unidentified visits still increment **box** totals; per-cat only when `pet_id`/`name` known; optionally track **Unknown** as a bucket.  
- Multi-box: pet metrics **sum across boxes** for that account entry; favorite is the device with max visits.

### 6.3 Favorite box definition

```text
favorite(pet) = argmax over boxes of count(visit_ended for pet on box in 30d)
tie-break = most recent visit_ended
if total visits for pet < 3 → "Not enough data"
```

---

## 7. Proposed HA entity map (implementers)

Keep entities **lean**. Prefer clear names. Use `entity_category=diagnostic` only for debug noise—not for primary cat-care signals. All durations: native **seconds** + `DURATION` (or hours as plain sensors with unit `h` if clearer—pick one and stick to it; **recommend seconds + device class**).

**Live API entities** (occupancy, weight, controls, errors, stats) are governed by **§3A** (must be visible if BA-useful). **§7.2–7.7** extend that with Layer B analytics. When §3A.5 and §7 disagree, §3A wins for live R/R/W fields; §7 wins for derived chore/visit rollups.

### 7.1 Per litter box (device) — live (mostly exists)

| Entity | Type | Status |
|--------|------|--------|
| Cat in litter box | binary | Done |
| Waste bin full | binary | Done |
| Cat weight | sensor | Done (g + suggested mass unit) |
| Daily uses | sensor | Done (today) |
| Average daily duration | sensor | Done (today) |
| Empty / Pack | button | Done |

### 7.2 Per litter box — identity & visits (new)

| Suggested name | Type | Metric IDs |
|----------------|------|------------|
| Occupying pet | sensor (text) | V5 |
| Last visitor | sensor (text) | V7 |
| Visits (7 days) | sensor | V9 |
| Visits (30 days) | sensor | V9 |
| Avg visit duration (30d) | sensor | V11 |

*(Today’s visits/duration can keep existing entities.)*

### 7.3 Per litter box — full-bag response (new) ⭐

| Suggested name | Type | Metric ID |
|----------------|------|-----------|
| Time full (current) | sensor (duration) | `full.current_waiting_s` |
| Last time-to-clear | sensor (duration) | `full.last_time_to_clear_s` |
| Avg time-to-clear (30d) | sensor | `full.avg_time_to_clear_s_30d` |
| Max time-to-clear (30d) | sensor | `full.max_time_to_clear_s_30d` |
| Full episodes (30d) | sensor | `full.episodes_30d` |

### 7.4 Per litter box — bag lifetime (new) ⭐

| Suggested name | Type | Metric ID |
|----------------|------|-----------|
| Last bag replaced | timestamp | `bag.last_replaced_at` |
| Hours since bag replaced | sensor | `bag.hours_since_replaced` |
| Last bag lifetime | sensor (duration) | `bag.last_lifetime_hours` |
| Avg bag lifetime (30d) | sensor | `bag.avg_lifetime_hours_30d` |
| Bags replaced (30d) | sensor | `bag.count_replaced_30d` |
| Visits during last bag | sensor | `bag.visits_during_last_bag` |

### 7.5 Per litter box — litter reset (new) ⭐

| Suggested name | Type | Metric ID |
|----------------|------|-----------|
| Last litter reset | timestamp | `litter.last_reset_at` |
| Hours since litter reset | sensor | `litter.hours_since_reset` |
| Last litter interval | sensor | `litter.last_interval_hours` |
| Avg litter interval (30d) | sensor | `litter.avg_interval_hours_30d` |
| Litter resets (30d) | sensor | `litter.resets_30d` |
| Mark litter reset | button | helper if no API (D7) |

### 7.6 Per litter box — pack (new)

| Suggested name | Type | Metric ID |
|----------------|------|-----------|
| Last pack | timestamp | `pack.last_at` |
| Hours since last pack | sensor | `pack.hours_since` |
| Avg hours between packs (30d) | sensor | `pack.avg_hours_between_30d` |
| Packs (30d) | sensor | `pack.count_30d` |
| Visits since last pack | sensor | `pack.visits_since_last` |

### 7.7 Per pet (device)

| Entity | Type | Notes |
|--------|------|-------|
| (device name = pet name) | device | From API |
| Weight | sensor | If API provides |
| Visits today / 7d / 30d | sensor | |
| Avg visit duration (30d) | sensor | |
| Favorite litter box | sensor | Name or **Not enough data** |
| Last seen | timestamp | Last visit_ended |

### 7.8 States for empty / unknown (UI contract)

| Situation | State / display | Attributes |
|-----------|-----------------|------------|
| No packs in 30d | **None in last 30 days** (or `none`) | `reason=no_events_in_window` |
| No completed bag lifetimes | **None** | `completed_cycles=0` |
| Never bag replaced | **Never** | |
| Pet not identified | **Unknown** | |
| &lt;3 visits for favorite | **Not enough data** | `visit_count` |
| Litter source unknown | **Unavailable** | `reason=litter_reset_source_unknown` |
| Average of empty set | **None**, never `0` | |

Use translation keys for every user-facing string.

### 7.9 Entity enablement (lean Gold)

| Default enabled | Default disabled (user can enable) |
|-----------------|------------------------------------|
| Full current wait, last/avg time-to-clear | min/median time-to-clear |
| Last/avg bag lifetime, hours since bag | min/max bag lifetime |
| Last/avg litter interval, hours since reset | add→reset lag until model B |
| Packs 30d, visits since pack | — |
| Occupying pet, visits 30d, favorite box | weight history series |

---

## 8. Windows, retention, timezone

| Window | Definition | Use |
|--------|------------|-----|
| **Today** | Calendar day in **HA local timezone** | Align with wcheader when possible |
| **7 days** | Rolling 7 × 24h from `now` | Week trends |
| **30 days** | Rolling 30 × 24h from `now` | “Past month” / averages |
| **Event retention** | 90 days raw events, daily prune | Pi-safe default |
| **Unlimited history** | Out of scope for default | Optional future export |

**Average rules:**

- Averages are over **completed intervals/episodes** with an end timestamp in the window.  
- Open cycles (current bag age, current full wait) are **live sensors**, not included in “avg lifetime” until closed.  
- Sample size attribute: `sample_count` on every average sensor (for trust).

---

## 9. Discovery checklist (blockers)

Capture via debug log or diagnostics (**no secrets**):

| # | Capture | Unblocks |
|---|---------|----------|
| 1 | `GET /app/v1/pet/list` redacted JSON (keys + types) | Pet roster |
| 2 | `properties/get` while **known named** cat is in box | Occupying pet |
| 3 | Same for **unknown/guest** weight | Unknown behavior |
| 4 | Sequence: full → pack → empty → new bag (app + properties timeline) | Bag close definition, inference |
| 5 | App **litter reset** after adding litter (endpoint/property) | Litter analytics without helper |
| 6 | App strings for Unknown (EN + user locales) | i18n parity |
| 7 | Whether Pack alone clears error 16 | time-to-clear `cleared_how` |
| 8 | Full redacted `property_keys` list from live diagnostics (all boxes/models) | Complete §3A.5 matrix; no silent BA-useful fields |
| 9 | Which properties are **settable** (app write capture) | Read/write parity for sleep, litter reset, etc. |
| 10 | Meaning of `completionStatus`, `excreteTimesEveryday`, `excreteTimerEveryday` | Correct sensors vs duplicates of wcheader |

Until (2)–(3) land, **Occupying pet** may stay **Unknown** without guessing.  
Until (5) lands, ship **Mark litter reset** helper so litter intervals still work.  
Until (8)–(10) land, treat known keys in §3A.5 as minimum; **any new key** from diagnostics enters the BA value test before the next release.

---

## 10. Phased delivery

| Phase | Cat-lover value | Depends on | Ships |
|-------|-----------------|------------|-------|
| **P0 Discovery** | Unblocks truth + full property inventory | Live capture | Docs/fixtures; update §3A.5 |
| **P0b API visibility gaps** | HA can automate on data we already fetch | Known keys only | §3A.7 P1 rows (diffs, firmware, completion, problem binaries, handMode state)—**no new HTTP** |
| **P1 Pet roster** | See all cats | pet/list schema | Pet devices/names; full-poll pets |
| **P2 Live identity** | Name or Unknown in box | P0 property capture | Occupying pet |
| **P3 Visit event log** | Day/7d/30d; avg duration; favorite | Occupancy edges + optional identity | Visit sensors |
| **P4 Full + pack/empty chore log** | Time-to-clear last/avg/max; pack intervals | Waste full binary + buttons | §7.3, §7.6 |
| **P5 Bag lifetime** | How long bags last; last/avg | Bag close definition + empty/pack events | §7.4 |
| **P6 Litter reset** | Intervals last/avg; hours since | Reset API **or** helper button | §7.5 |
| **P7 Polish** | Blueprints, dashboard card, enablement tuning | P3–P6 stable | UX |

**Ordering note:** **P0b can ship immediately**—it only maps fields already in the poll payload (performance-safe). P4 can ship before P5. P6 can ship with helper button before API discovery.

**Do not ship** “30-day” metrics that only re-label today’s wcheader.  
**Do not ship** raw untranslated property dumps as primary entities—always proper platforms (§3A.3).

---

## 11. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Performance | Event append O(1); rollups incremental or cheap recompute; no history pull every 30s; **§3B budget** |
| API visibility | BA-useful R and R/W fields → HA entities/attributes (§3A); diagnostics is not enough |
| HA practices | Correct platform, device class, entity category, translations, stable unique_id, quality scale Gold-lean |
| Responsiveness | Command → visible state update without waiting full 5 min poll |
| Pi | Cap events (90d); avoid unbounded RAM; prune daily; default-enabled entity count disciplined |
| Privacy | Pet names local; diagnostics redact tokens/passwords |
| Honesty | **None** / **Unknown** / **Unavailable** / **Never** over invented math |
| Multi-box | Chores per `iotid`; pets account-scoped |
| Restart safety | Persist open full episode + last bag/litter markers |
| i18n | All strings via translation keys |
| Tests | Unit tests for state machines (bag, full episode, litter debounce) + rollup windows + entity mapping for new API keys |
| Docs | README “supported functions” updated whenever §3A.5 status changes |

---

## 12. Acceptance scenarios (QA / product)

### 12.1 Pets & visits

1. **Named visit:** Known cat enters → Occupying pet = “Mochi”; visit ends → duration stored; Mochi visits today += 1.  
2. **Unknown visit:** Unidentified → Occupying pet = **Unknown**; box visit totals still increment.  
3. **Favorite box:** Mochi 20 visits A, 5 visits B in 30d → Favorite = A.  
4. **Not enough data:** Mochi 2 visits total → Favorite = **Not enough data**.

### 12.2 Full bag time-to-clear ⭐

5. **Normal clear:** Full at 10:00, cleared 12:30 → last time-to-clear = **2.5h**; contributes to 30d avg.  
6. **Live wait:** Full at 10:00, still full at 11:00 → Time full (current) ≈ **1h**; last time-to-clear unchanged.  
7. **No fulls in month:** episodes 30d = 0 → avg/max = **None in last 30 days**.  
8. **Blip ignore:** Full true for one 30s poll only → no episode.  
9. **Max shame metric:** Episodes 30m, 40m, 6h → max = **6h**, avg ≈ **2.3h**.

### 12.3 Bag lifetime ⭐

10. **First replace only:** One Empty after install → last bag replaced set; last/avg lifetime = **None** (need two closes).  
11. **Completed lifetime:** Replace Mon 12:00, next replace Fri 12:00 → last bag lifetime = **4.0 days**.  
12. **Avg:** Lifetimes 4d, 5d, 6d ending in 30d → avg = **5.0 days**.  
13. **Preemptive empty:** Empty without full still closes bag cycle.  
14. **None in month:** No completed pairs in 30d → avg = **None in last 30 days**.  
15. **Visits on bag:** 47 visits between two replaces → visits during last bag = **47**.

### 12.4 Litter reset ⭐

16. **Two resets:** Jan 1 and Jan 20 → last interval = **19 days**.  
17. **Avg:** Intervals 7d, 9d, 8d in window → avg = **8 days**.  
18. **Hours since:** Last reset 6d ago → hours since ≈ **144**.  
19. **None:** No reset in 30d → avg = **None in last 30 days**; count = 0.  
20. **Debounce:** Two resets 2 minutes apart → one interval (ignore second for pairing).  
21. **Helper button:** User presses “Mark litter reset” without vendor API → events and sensors update.

### 12.5 Pack

22. **No packs in month:** Packs (30d) = 0; avg interval = **None in last 30 days**.  
23. **Visits since pack:** 14 visits after last pack → sensor = 14.

---

## 13. Open decisions log

| ID | Decision | Default until owner says otherwise |
|----|----------|-------------------------------------|
| D1 | Bag cycle closes on Empty vs Pack vs either | **Empty** preferred; config `bag_cycle_closes_on` later |
| D2 | Month = rolling 30d vs calendar month | **Rolling 30d** |
| D3 | Unknown string | **"Unknown"** + i18n |
| D4 | Min visits for favorite box | **3** |
| D5 | Debounce visit flaps | **20s** |
| D6 | Full must persist N polls | **2** presence polls |
| D7 | Litter reset without API | Helper button **yes** as fallback |
| D8 | First bag close counts as lifetime? | **No** — need 2 closes for duration |
| D9 | Include vacation outliers in avg time-to-clear? | **Yes** in avg; always expose **max**; optional median later |
| D10 | Duration unit in UI | Native seconds + duration device class; cards may show d/h |
| D11 | Double empty debounce | **5 minutes** |
| D12 | Double litter reset debounce | **10 minutes** |
| D13 | BA-useful API field without entity | **Not allowed** for release once field is understood—must entity, attribute (with reason), or documented BA-skip |
| D14 | Duplicate wcheader vs excrete* properties | Prefer one primary sensor; other as attribute or disabled-by-default after validation |
| D15 | New property keys from field diagnostics | Must pass §3A.2 before next minor version or be listed BA-skip |

---

## 14. Developer implementation sketch (non-binding)

Suggested modules (names illustrative):

| Module | Responsibility |
|--------|----------------|
| `analytics/store.py` | Append, query, prune events |
| `analytics/edges.py` | Diff consecutive coordinator data → visit/full edges |
| `analytics/commands.py` | Hook successful Empty/Pack/helper reset → events |
| `analytics/cycles.py` | Bag state machine, full episodes, litter intervals |
| `analytics/rollups.py` | last/avg/min/max/count for 7d/30d |
| `sensor.py` / platforms | Live API entities (§3A) **and** rollup entities (§7) |
| `device_entities.py` | Single place that lists what a box exposes (keep matrix honest) |
| tests | Cycles + rollups + **property→entity mapping** for each BA-required key |

**Coordinator integration:** After each presence/full update, run edge detectors. On button press success, emit command events immediately (don’t wait for next poll).

**Visibility integration:** When adding a coordinator field, add the entity in the same PR (or explicit BA-skip note in §3A.5). No “fetch now, expose later” without a tracked gap row.

---

## 15. Methodical backlog checklist (cat-lover BA sign-off)

Use this as the “did we think it through?” list before coding.

### Pets & health

- [ ] Named pets from roster  
- [ ] Unknown never faked  
- [ ] Who is in the box now  
- [ ] Last visitor  
- [ ] Visits today / 7d / 30d per box  
- [ ] Visits today / 7d / 30d per cat  
- [ ] Avg visit duration today / 30d per box  
- [ ] Avg visit duration 30d per cat  
- [ ] Favorite box per cat + not-enough-data  
- [ ] Weight live (done); per-cat history if identifiable  

### Chores — bags ⭐

- [ ] Last bag replaced timestamp  
- [ ] Hours/days current bag has been in use  
- [ ] Last completed bag lifetime  
- [ ] Average bag lifetime (30d)  
- [ ] Min/max bag lifetime (30d) optional  
- [ ] Bags replaced count (30d)  
- [ ] Visits (and packs) during a bag  
- [ ] Clear empty states (Never / None)  
- [ ] Works when empty happens outside HA (inference)  
- [ ] First replacement doesn’t invent a lifetime  

### Chores — full bag take-out ⭐

- [ ] Live “how long has it been full”  
- [ ] Last time-to-clear  
- [ ] Avg time-to-clear (30d)  
- [ ] Max time-to-clear (30d)  
- [ ] Episode count (30d)  
- [ ] Debounced full edges  
- [ ] Restart-safe open episode  
- [ ] Distinct from bag lifetime  

### Chores — litter + reset ⭐

- [ ] Last reset time  
- [ ] Hours since reset  
- [ ] Last interval between resets  
- [ ] Avg interval (30d)  
- [ ] Reset count (30d)  
- [ ] Helper button if no API  
- [ ] Debounce double reset  
- [ ] Document reset-only vs add+reset models  

### Chores — pack

- [ ] Last pack / hours since / avg gap / count  
- [ ] Visits since last pack  

### Trust & quality

- [ ] No fake 30d from today’s wcheader only  
- [ ] sample_count on averages  
- [ ] i18n for None/Unknown/Never  
- [ ] Pi retention 90d  
- [ ] Tests for state machines  

### API visibility & HA best practices ⭐

- [ ] Every BA-useful **read** field visible as entity (or justified attribute)  
- [ ] Every BA-useful **read/write** field has state **and** control in HA  
- [ ] No BA-useful data only in diagnostics JSON  
- [ ] Correct platforms (binary_sensor / sensor / switch / button / select)  
- [ ] Device classes, units, translations, entity categories  
- [ ] Default-enabled vs disabled-by-default chosen for calm UX  
- [ ] No extra HTTP on presence poll for vanity fields  
- [ ] Pets polled only on full path when pet entities exist  
- [ ] Command success refreshes state promptly  
- [ ] §3A.5 matrix updated when diagnostics shows new keys  
- [ ] README supported functions matches shipped entities  
- [ ] Performance budget §3B respected  

### Already-fetched but not fully visible (P0b candidates)

- [ ] wcheader `times_diff` / `avg_diff`  
- [ ] `completionStatus`  
- [ ] Current `handMode` (diagnostic)  
- [ ] Cover open / drawer / richer error binaries  
- [ ] Firmware / product diagnostic sensors  
- [ ] Validate `excreteTimesEveryday` / `excreteTimerEveryday` vs wcheader  

---

## 16. Summary for stakeholders

| Theme | Status |
|-------|--------|
| Pet names + weight | Feasible via **pet/list** (+ fields TBD); not in 1.2.x today |
| Name when cat in box / Unknown | Feasible **if** live properties (or reliable weight ID) provide it; else Unknown only |
| Month averages, favorite box | **Local event analytics** |
| **Bag lifetime** (last, avg, current age, visits/bag) | **In scope** — Empty/Pack + state machine; discovery refines close rule |
| **Time-to-clear full bag** (last, avg, max, live wait) | **In scope** — from existing waste-full signal + episode log |
| **Litter reset intervals** (last, avg, hours since) | **In scope** — needs discovery **or** helper button day one |
| Pack frequency + visits since pack | **In scope** — HA buttons + optional inference |
| **API R + R/W → visible in HA** | **In scope product rule (§3A)** — map BA-useful fields to proper entities; P0b for zero-cost gaps; never leave automatable data only in diagnostics |
| HA best practices + performance | **Required** — Gold-lean platforms/categories; dual poll; §3B budget; lean default entity set |
| Unlimited history | **Not default**; 90-day events |

### What “awesome for cat lovers” means when this is done

A multi-cat household can open **Home Assistant** (not only the vendor app) and:

1. **See and automate on** every helpful live signal the API already provides (occupancy, weight, full, errors, locks, modes, stats, …).  
2. **Control** what the API allows (clean, empty, pack, auto, DND, delay, lock, …) with correct HA switches/buttons/selects.  
3. Know **who** used which box and for how long (or Unknown).  
4. Know **which box** each cat prefers.  
5. Know **how long bags last**, **how long full bags sit**, and **how long litter lasts** between resets—with last + averages.  
6. Enjoy a **fast, calm, trustworthy** integration: right units, clear names, no fake data, no sluggish poll spam.

---

*This document is the single source of truth for implementing multi-cat + chore analytics **and** complete BA-useful API visibility on Furbulous HA—without inventing API capabilities, and without hiding automatable data from Home Assistant.*
