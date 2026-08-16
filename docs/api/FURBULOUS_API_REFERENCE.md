# Furbulous cloud API reference ( empirically verified )

**Status:** Living document. Prefer this over code comments or prior assumptions.  
**Last updated:** 2026-08-16 (PDT session)  
**Primary device:** Downstairs (`device_id` 3139) — US region account  
**Ground rules:** No Empty (`handMode` 2) or Pack (`handMode` 3) during discovery unless explicitly authorized.

Related:

- Physical display checks: [`captures/physical_check_display_2026-08-15.jsonl`](captures/physical_check_display_2026-08-15.jsonl)
- Redacted snapshot: [`captures/downstairs_snapshot_redacted.json`](captures/downstairs_snapshot_redacted.json)
- Quality prompts: [`../../tests/quality/PROMPTS.md`](../../tests/quality/PROMPTS.md)

---

## 1. How to use this document

1. **Before changing HA entities**, re-read the relevant section and the “Verified vs assumed” table.  
2. **Physical panel state** is required for display semantics — API bits alone were wrong for months of troubleshooting.  
3. **Pet weights:** account roster `unit=1` is **pounds** on this US account (see §7).  
4. **Do not invent endpoints.** Only list what returned `code=0` with real data in probes.

---

## 2. Transport & auth

| Item | Value (US) |
|------|------------|
| Client | iOS-style headers (`appid`, `version`, `platform`, `sign` = MD5(appid+path+ts)) |
| Auth | `POST /app/v1/auth/login` with email/password/account_type |
| Authenticated calls | Bearer/token from login (see `furbulous_api.py`) |
| Regions | `us` / `eu` / `asia` hosts (see `regions.py`) |

Integration implementation: `custom_components/furbulous/furbulous_api.py`.

---

## 3. Core endpoints (verified)

| Method | Path | Purpose | Verified |
|--------|------|---------|----------|
| POST | `/app/v1/auth/login` | Login | Yes |
| GET | `/app/v1/device/list` | Devices (name, iotid, online, `is_disturb`, version, …) | Yes |
| GET | `/app/v1/device/properties/get?iotid=` | Live properties map | Yes |
| POST | `/app/v1/device/properties/set` | Body `{ "iotid", "items": { key: value } }` | Yes (selected keys) |
| GET | `/app/v1/device/data/wcheader?iotid=` | Daily summary: times, avg_duration, diffs | Yes |
| GET | `/app/v1/device/data/wc?iotid=` | **Visit history**: start_time, weight (g), duration | Yes |
| GET | `/app/v1/pet/list` | Account pet roster | Yes |
| GET | `/app/v1/device/info?iotid=` | Device meta (mac, software, hardware, icon, …) | Yes |
| PUT | `/app/v1/device/disturb` | Body `{ "iotid", "is_disturb": 0\|1 }` | API returns OK; **list bit may not stick** (see §6) |

### Endpoints probed with no useful data (2026-08)

Many guessed history paths returned non-zero codes or empty data. **Do not rely on them** unless re-verified:

- `/device/data/history`, `/device/record/list`, `/device/event/list`, `/device/excrete/list`, `/pet/history`, etc.

**Use `/device/data/wc` for activity**, not inventing new history APIs.

---

## 4. Device list fields (sample)

Per device on list:

| Field | Meaning (observed) |
|-------|---------------------|
| `id` | Numeric device id (HA uses this) |
| `iotid` | Cloud device id for properties |
| `name` | User label (e.g. Downstairs) |
| `device_online` | 1 online |
| `is_disturb` | Quiet hours / DND active bit (0/1) |
| `version` / product fields | Firmware marketing string |
| `active_time` | Last activity unix (when present) |

Account under test: **Downstairs, Upstairs, Master** — all online during session.

---

## 5. Properties map (Downstairs, 2026-08-15)

Values flattened from `{ value, time }` wrappers.

| Property | Example | Writable? | Notes |
|----------|---------|-----------|--------|
| **DisplaySwitch** | 0 or 1 | **Yes** | **Primary physical display control** — see §5.1 |
| **masterSleepOnOff** | 0 or 1 | **Yes** | HA “Screen off” today; **did not change panel** in physical tests when DisplaySwitch=1 in window |
| **displayStartTime** | 1380 | **Yes** | Minutes from midnight → **23:00** |
| **displayEndTime** | 420 | **Yes** | Minutes from midnight → **07:00** (overnight window) |
| **sleepTimeStart** | 720 | **Yes** | **12:00** — likely Quiet hours / night schedule start |
| **sleepTimeStop** | 360 | **Yes** | **06:00** — schedule end (overnight wrap) |
| FullAutoModeSwitch | 1 | Yes (integration) | Auto-clean after visits |
| catCleanOnOff | 4 | Yes | Minutes before auto-clean (1–30) |
| childLockOnOff | 0 | Yes | Child lock |
| workstatus | 0 | Read | 0 idle; 1 cat present (occupancy) |
| catWeight | 10805 | Read | **Grams** (last measured / sticky) |
| errorReportEvent | 0 | Read | Bitfield errors (16=full, 64=drawer, 128=cover, …) |
| handMode | 0–5 | Write (momentary) | 1 clean, 2 empty, 3 pack, 4 pause, 5 resume — **do not use 2/3 without user OK** |
| completionStatus | 1 | Read | Best-effort cycle complete |
| unitSwitch | 1 | Read | Device unit preference bit (see §7) |
| ConnectType | online | Read | |
| catLitterType | 0 | Read | |
| catBathroomTimeStart/Stop | e.g. 1239 | Read | Minutes-of-day ≈ last visit (~20:39 vs visit 20:37) |
| excreteTimesEveryday | 1 | Read | Daily count (may lag wcheader) |
| excreteTimerEveryday | 28 | Read | Duration-related |
| LocalTime | large int | Read | **Not decoded** as unix; do not trust for TZ until reverse-engineered |
| mcuversion / wifivertion / … | strings | Read | Firmware |
| timingShoveledShit | hex string | Read | Opaque schedule blob — do not invent meaning |
| otastatus | 0 | Read | OTA |

### 5.1 Display control — **physically verified** (2026-08-15 ~23:52–23:56 PDT)

Wall clock: **PDT**. Display window on device: **23:00–07:00** (`displayStartTime=1380`, `displayEndTime=420`).

| Step | API write | User observed panel |
|------|-----------|---------------------|
| Baseline | DisplaySwitch=1, masterSleepOnOff=0, in window | **Dark** |
| A | **DisplaySwitch → 0** | **Lit** |
| B | **DisplaySwitch → 1** | **Dark** |
| C | masterSleepOnOff → 1 (DisplaySwitch=1) | **Dark** (no change) |
| D | masterSleepOnOff → 0 (DisplaySwitch=1) | **Dark** (still dark) |
| E | **DisplaySwitch → 0** | **Lit** |

#### Correct product model (evidence-based)

| Desired UX | API |
|------------|-----|
| **Always on** (force lit) | `DisplaySwitch = 0` |
| **Scheduled blanking** | `DisplaySwitch = 1` + `displayStartTime` / `displayEndTime` (minutes from midnight). Inside window → blank; outside → lit (expected; **daytime window not yet physically re-tested**) |
| **Always off** | Not fully proven in isolation. Candidates: `DisplaySwitch=1` with full-day blank window, and/or `masterSleepOnOff=1`. **Needs a daytime physical test** (outside 23:00–07:00) to separate schedule from force-off. |

#### What HA got wrong historically

- Mapped **Screen off** only to **`masterSleepOnOff`**.  
- Ignored **`DisplaySwitch`** (the bit that matched the panel).  
- Looked for non-existent `masterSleepStartTime` keys; real keys are **`displayStartTime` / `displayEndTime`**.  
- Assumed polarity “1 = screen power off” for DisplaySwitch — **opposite for force-on** (`0` = lit).

#### Timezone note

During the night session, “inside window” was true for both **PDT wall clock** and a naïve **UTC wall clock** interpretation of the same minute numbers (because overnight windows overlap). **That does not prove times are UTC.**  

Treat `display*` / `sleep*` as **minutes from midnight in the house’s intended local schedule** until a controlled test proves otherwise:

**Recommended TZ test (when user available):**  
1. Note PDT time and panel state with DisplaySwitch=1.  
2. Temporarily set `displayStartTime`/`displayEndTime` to a **narrow 15-minute window that only makes sense in local time** (e.g. start = now+2 min local, end = now+17 min).  
3. Observe blanking only in that window.  
4. Restore previous times.  
Do **not** leave experimental windows active overnight without user OK.

---

## 6. Quiet hours / DND

| Mechanism | Observed |
|-----------|----------|
| Enable bit | Device list `is_disturb` + `PUT /device/disturb` |
| Schedule | **`sleepTimeStart` / `sleepTimeStop`** (writable) — Downstairs was **12:00–06:00** |
| Physical cleaning suppression | **Not verified** this session (user rarely uses DND) |

**API anomaly:** `set_device_disturb(True)` returned success but **`is_disturb` remained 0** on immediate device list re-read for all boxes. Possible delay, wrong field, or account/device quirk. **Do not claim DND toggle works until app + list bit + motor silence are co-verified.**

HA should map Quiet hours **times** to `sleepTime*`, not invent 22:00–08:00 defaults.

---

## 7. Units & weights

### 7.1 Device weight

- Property **`catWeight`** and WC history **`weight`** are **grams**.  
- Example: `10805` g ≈ **23.82 lb** (Tigger).  
- HA under **US Customary** must show **lb**, not divide by 1000 and show “10.805” (that was **kg-style** mis-display).

### 7.2 Pet roster weights

| Field | Observed |
|-------|----------|
| `nickname` | Display name |
| `pet_id` | Id |
| `weight` | Small number (7, 10, 17, 24, 14 after full roster) |
| `unit` | **1** on this US account |

**Evidence `unit=1` means pounds (this account):**

- User: Jet **17.4 lb**, Tigger **23.8 lb**, Vinnie **~7.3**, Paulie **~9.3**.  
- API after roster update: Jet **17**, Tigger **24**, Vinnie **7**, Paulie **10** (rounded).  
- WC visits: **7882 g ≈ 17.4 lb**, **10805 g ≈ 23.8 lb** — match Jet/Tigger when roster is interpreted as **lb → g**.

**Bug in current HA code:** `extract_pet_weight_grams` treats bare `weight < 80` as **kg** (`×1000`). That makes Jet 17 → 17000 g (wrong) or Vinnie 7 → 7000 g (wrong for lb). **Must use `unit` (and/or region) before matching.**

### 7.3 Multi-account pets

Roster is **per login**. Cats added on a linked spouse account may not appear until added/visible on this login. After user added Jet/Tigger/Cleo, list was complete for matching.

---

## 8. Visits, activity, cat identity

### 8.1 API activity (source of truth for history)

`GET /app/v1/device/data/wc?iotid=`

```json
{
  "start_time": 1786804513,
  "weight": 10482,
  "duration": "0分32秒",
  "minute": 0,
  "second": 32
}
```

- **No pet name or pet_id** on records.  
- Identity = **closest roster weight** (app-style), after correct unit conversion.  
- Daily `wcheader.times` matched **3** WC rows for Downstairs that day.

### 8.2 Live occupancy

- `workstatus == 1` → cat in box (30s poll).  
- Live `catWeight` often sticky last visit weight when empty.

### 8.3 What HA did wrong

- Only recorded visits from **occupancy edges after connect** → **Last cat / Last visit empty** despite WC history.  
- Should **hydrate from `/device/data/wc`** (and optionally merge live edges).  
- Matching without Jet/Tigger on roster → wrong names; without lb unit → wrong deltas.

### 8.4 Expected match (after unit fix + full roster)

| Visit weight | ≈ lb | Closest cat (lb roster) |
|--------------|------|-------------------------|
| 7882 g | 17.4 | Jet (~17) |
| 10482–10805 g | 23.1–23.8 | Tigger (~24) |

---

## 9. Daily stats (`wcheader`)

| Field | Meaning |
|-------|---------|
| `times` | Uses today |
| `avg_duration` | Average duration (seconds observed) |
| `times_diff` | vs yesterday |
| `avg_diff` | duration delta vs yesterday |

---

## 10. Commands (write) — safety

| Action | How | Safety |
|--------|-----|--------|
| Manual clean | `handMode: 1` | OK to test with user watching box |
| Pause / Resume | `handMode: 4` / `5` | OK |
| **Empty** | `handMode: 2` | **Destructive — user authorize only** |
| **Pack / seal** | `handMode: 3` | **User authorize only** |
| Auto-clean / delay / child lock | FullAutoModeSwitch, catCleanOnOff, childLockOnOff | Safe config |
| Display force on | DisplaySwitch=0 | Safe; verified |
| Display scheduled mode | DisplaySwitch=1 + times | Safe; blanking in window verified at night |
| DND | disturb API | Unverified stickiness |

---

## 11. Desired HA UX (product, not yet implemented)

Agreed direction:

**Screen mode** (one select):

1. **Always on** → `DisplaySwitch=0`  
2. **Always off** → TBD physical daytime test  
3. **Scheduled** → `DisplaySwitch=1` + `displayStartTime`/`displayEndTime`  

Keep power users’ raw attributes / events.

**Do not ship** more Screen off = `masterSleepOnOff` as the only control.

---

## 12. Verified vs assumed

| Topic | Status |
|-------|--------|
| DisplaySwitch 0 = lit | **Verified** (physical) |
| DisplaySwitch 1 + night window = dark | **Verified** (physical) |
| masterSleepOnOff alone controls panel | **Falsified** in these tests |
| displayStart/End minutes local wall | **Likely**; TZ not fully proven |
| sleepTime* = Quiet hours schedule | **Assumed** (writable; app not co-checked) |
| disturb API enables quiet hours | **Uncertain** (bit didn’t stick) |
| unit=1 → lb | **Strongly evidenced** this account |
| WC history for activity | **Verified** |
| Pet name on WC records | **Absent** |
| Empty/Pack semantics | Prior knowledge only; not re-tested here |

---

## 13. Physical test protocol (repeatable)

Use with a human at the box. Log API before/after each step.

1. Record wall-clock timezone and time.  
2. Read DisplaySwitch, masterSleepOnOff, displayStart/End.  
3. Set DisplaySwitch=0 → expect **lit** → user confirms.  
4. Set DisplaySwitch=1 → if now ∈ [start,end] overnight window → expect **dark**.  
5. Toggle masterSleepOnOff only if isolating that bit.  
6. Restore user-preferred mode (often DisplaySwitch=0 for always on).  
7. **Never** handMode 2/3 without explicit OK.

---

## 14. Open questions (for next session)

1. **Always off:** Outside 23:00–07:00, with DisplaySwitch=1, is the panel lit? With DisplaySwitch=1 and a window that covers all 24h, does it stay dark?  
2. **Daytime schedule:** Blank only in a 15-minute local window to prove TZ.  
3. **masterSleepOnOff** app label vs DisplaySwitch.  
4. **DND:** App toggle vs `is_disturb` vs `sleepTime*`.  
5. **Cleo** weight once first visit exists.  
6. **Linked accounts:** whether both logins share identical pet list weights always.

---

## 15. Integration implementation checklist

- [x] Screen mode select: **Always on** / **Scheduled** (`DisplaySwitch`)  
- [x] Stop using masterSleepOnOff as sole “Screen off” (switch removed; mode select)  
- [x] Map schedule times to `displayStartTime`/`displayEndTime` (minutes)  
- [x] Map Quiet hours times to `sleepTimeStart`/`sleepTimeStop`  
- [x] Ingest `/device/data/wc` into analytics / Last cat / Last visit (when API returns rows — often **today-only**)  
- [x] Fix pet weight: `unit==1` → pounds → grams; normalize `nickname`/`pet_id`  
- [x] Fix HA weight display for US Customary (lb) when unit system is US  
- [x] UAT tests for screen mode + unit=1 lb matching  
- [x] Quality PROMPTS point at this doc  

### WC history note (2026-08-16 ~00:00 PDT)

`GET /device/data/wc` returned **[]** after local midnight even though Aug 15 visits existed earlier the same calendar evening. Treat WC as **rolling “today” (device/cloud day boundary)** — Last cat hydrates when visits exist for the current cloud day; older days need live occupancy or a future dated query if discovered.

---

## 16. Capture index

| File | Content |
|------|---------|
| `captures/physical_check_display_2026-08-15.jsonl` | Step log + API echoes |
| `captures/downstairs_snapshot_redacted.json` | Properties, pets, WC visits (no secrets) |

**End of reference.** Update date and “Verified” tables when new physical or endpoint evidence lands.
