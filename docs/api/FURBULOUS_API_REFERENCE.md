# Furbulous cloud API reference ( empirically verified )

**Status:** Living document. Prefer this over code comments or prior assumptions.  
**Last updated:** 2026-08-16 (PDT; jammed trash-door Clean + on-box OK)  
**Primary device:** Downstairs (`device_id` 3139) — US region account  
**Ground rules:** No Empty (`handMode` 2) or Pack (`handMode` 3) during discovery unless explicitly authorized.

Related:

- Physical display checks: [`captures/physical_check_display_2026-08-15.jsonl`](captures/physical_check_display_2026-08-15.jsonl)
- Redacted snapshot: [`captures/downstairs_snapshot_redacted.json`](captures/downstairs_snapshot_redacted.json)
- Three-box compare (Upstairs full=`32`): [`captures/three_box_compare_2026-08-16.json`](captures/three_box_compare_2026-08-16.json)
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
| Auth | `POST /app/v1/auth/login` with email/password/account_type — **once per HA session** |
| Authenticated calls | Reuse the login **token** on every request (`authorization` header). Cheap per-request `sign` is only MD5(appid+path+ts), not a new login. |
| Re-login | Only if there is no token yet, HTTP 401, or an explicit token/auth error code (`10401`/`10402`/`10403`, “invalid/expired token”). Unrelated “expired” strings do **not** re-login. |
| HTTP session | One shared `aiohttp` session per config entry (HA’s client session). |
| Regions | `us` / `eu` / `asia` hosts (see `regions.py`) |

Integration implementation: `custom_components/furbulous/furbulous_api.py`.

**Efficiency:** HA does **not** log in on every poll. Typical path: 1 login at setup / after token death, then Bearer reuse for the 30s property polls and 5 min full snapshot.

### 2.1 Dedicated Furbulous account (recommended)

The mobile app appears to allow **only one active login** for an account. When Home Assistant authenticates (setup, restart, or rare token refresh), that can **kick the phone app** and force you to sign in again.

Use a **dedicated Furbulous account** for this integration (create one in the app, share the boxes to it, put only those credentials in HA). Keep family phones on a different login. This is a user-observed vendor limitation, not something HA can fix.

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
| **masterSleepOnOff** | 0 or 1 | **Yes** | **Not used by HA** (1.3.9+). Did not change the panel in physical tests when DisplaySwitch=1 in window |
| **displayStartTime** | 1380 | **Yes** | Minutes from midnight → **23:00** |
| **displayEndTime** | 420 | **Yes** | Minutes from midnight → **07:00** (overnight window) |
| **sleepTimeStart** | 720 | **Yes** | **12:00** — likely Quiet hours / night schedule start |
| **sleepTimeStop** | 360 | **Yes** | **06:00** — schedule end (overnight wrap) |
| FullAutoModeSwitch | 1 | Yes (integration) | Auto-clean after visits |
| catCleanOnOff | 4 | Yes | Minutes before auto-clean (1–30) |
| childLockOnOff | 0 | Yes | Child lock |
| workstatus | 0 / 1 / 3 / **5** / **6** / **8** | Read | **0** idle. **1** clean or cat (not occupancy-only). **3** pack. **5** pour / brief post-reset. **6** after on-box litter reset (tail). **8** on-box litter reset rotation (~1 min). |
| catWeight | 10805 | Read | **Grams** (last measured / sticky) |
| errorReportEvent | 0 / **32** / **524352** | Read | **Bitwise** status. See §5.2. **0** = clear. **32** live-verified full. **524352** = 64\|524288 trash-door jam / screen **Device Failure E4**. **64 is not drawer-out.** **512** = lid off (not comms). |
| handMode | 0–6 | Write (sticky last command) | 1 clean, 2 empty, 3 pack, 4 pause, 5 resume, **6 = physical litter reset** (spread + tare; live Master 2026-08-16). Sticks at last command. Do not use 2/3 without user OK. |
| completionStatus | 1 / **3** / **5** | Read | **3** = clean running. **1** = clean finished. **5** = after on-box litter reset (not “Failed”). |
| unitSwitch | 1 | Read | Device unit preference bit (see §7) |
| ConnectType | online | Read | |
| catLitterType | 0 | Read | |
| catBathroomTimeStart/Stop | e.g. 1239 | Read | Minutes-of-day ≈ last visit (~20:39 vs visit 20:37); coarse vs WC |
| excreteTimesEveryday | 1 | Read | Daily count (may lag wcheader) |
| excreteTimerEveryday | 28 | Read | Duration-related |
| LocalTime | packed int | Read | **Device calendar date** — see §5.3 (not unix / not time-of-day) |
| mcuversion / wifivertion / … | strings | Read | Firmware |
| timingShoveledShit | hex string | Read | **Opaque** — see §5.4; do not use for clocks |
| otastatus | 0 | Read | OTA |

### 5.0a `LocalTime` packing (verified 2026-08-15/16 captures)

Sticky for the whole local calendar day (same value across multi-hour captures).

```text
LocalTime = (day << 24) | (month << 16) | ((year % 100) << 8) | flag
flag observed = 1
```

| Capture day | Value | Hex |
|-------------|------:|-----|
| 2026-08-15 | 252189185 | `0x0F081A01` |
| 2026-08-16 | 268966401 | `0x10081A01` |

**Use:** detect **day rollover** (compare previous vs current day/month/year). When the day key changes, treat `/device/data/wc` as a new “today” list (watermark reset). Do **not** treat `LocalTime` as a wall-clock timestamp.

HA helper: `custom_components/furbulous/device_time.py` (`decode_local_time`, `local_time_day_key`).

### 5.0b `timingShoveledShit` — scheduled scoop/clean slots (RE 2026-08-22)

Chinese product copy often uses **定时铲屎** (“timed shovel/scoop waste”). Live write tests (Downstairs, restore verified) show this property is a **writable packed schedule**, not related to `LocalTime` / WC clocks.

#### Observed live values (same account)

| Box | Value | Decoded |
|-----|-------|---------|
| Downstairs | `0700010007050100` | two slots (below) |
| Upstairs | `00` | empty / disabled |
| Master | *(absent)* | property missing |
| Cleo | *(absent)* | property missing |

#### Packing (best-supported hypothesis)

8-byte hex string = **two records × 4 bytes**:

```text
[hour][minute][enabled][reserved]  × 2
```

| Bytes | Interpretation |
|-------|----------------|
| `07 00 01 00` | **07:00**, enabled=`1`, reserved=`0` |
| `07 05 01 00` | **07:05**, enabled=`1`, reserved=`0` |
| `00` / `0000000000000000` | no slots / all disabled |
| `08 00 01 00 00 00 00 00` | **08:00** only (live write stuck) |
| `07 1E 01 00 07 05 01 00` | **07:30** + **07:05** (live write stuck; note `1E`=30) |

Hour/minute are **binary integers**, not BCD. `enabled` is `0`/`1`.

#### Write behavior (non-destructive probe, then restored)

- `properties/set` **accepts** `timingShoveledShit` and the value **persists** on readback.
- Writing the hex digit string alone works (`0700010007050100` → same).
- Bundling it with other keys in one set can **ASCII-hex-mangle** the payload (readback became `30373030…` = ASCII of `0700…` + NUL). Prefer **dedicated single-key writes**.
- Changing `sleepTimeStart`, `FullAutoModeSwitch`, or `catCleanOnOff` did **not** rewrite this blob to a new schedule (not a shadow copy of those fields).

#### Rejected / weak hypotheses

| Idea | Why rejected |
|------|----------------|
| Minutes-of-day uint16 (`displayEndTime=420`) | Layout is HH/MM bytes, not uint16 minutes |
| Shadow of sleep/display schedules | Sleep 12:00–06:00 / display 23:00–07:00 ≠ 07:00 & 07:05 slots; independent under writes |
| Pure DOW bitmask | Byte `07` as DOW mask possible but hour/min layout fits time-of-day far better |
| Opaque unused | **Falsified** — writable and structured |

#### Alignment with eco / screen / sleep (live 2026-08-22)

| Schedule | Keys | Downstairs example | Aligns with shovel? |
|----------|------|--------------------|---------------------|
| Screen eco | `DisplaySwitch` + `displayStart/EndTime` | 23:00→07:00 | **Weak:** shovel 07:00 equals `displayEnd`, +07:05; Upstairs also ends 07:00 but shovel=`00` |
| Quiet/sleep | `sleepTimeStart/Stop` | 12:00→06:00 | **No** — different window; shared across boxes with different shovel |
| Scoop slots | `timingShoveledShit` | 07:00 + 07:05 | Independent writable schedule |

**Exp A:** `displayEndTime +30` → shovel **unchanged**.  
**Exp B:** shovel set to **19:13 / 19:15** (near-now) → value stuck; through the window Downstairs stayed `workstatus=0` (no auto clean/pack). Control Upstairs idle.  
**Exp C / Clean now (Exp D):** Downstairs clean `workstatus=1` for minutes; shovel value **and** property `time` **unchanged** (`0700010007050100`).  
**Exp E — Seal/pack on Upstairs (2026-08-22):** `handMode: 3` → live `workstatus=3` (packing) then idle; `completionStatus` briefly `3`. Shovel stayed **`00`**; property `time` **unchanged** (sticky old stamp). Downstairs control shovel unchanged.  
**Exp F / G — arm near-now + user-observed clean (2026-08-22 ~19:35–19:41 PDT):**

| Step | Detail |
|------|--------|
| Arm | Downstairs shovel → `1324010013260100` = **19:36** + **19:38** (both enabled). Readback matched. |
| Cloud | `workstatus=1` from **19:35:12** (≈1–2 min *before* first slot) through **19:37:07**; idle by **19:37:14**. `handMode` stayed sticky `1` (same sticky pattern as after Clean). Shovel blob **unchanged** while cleaning. |
| User | Reported Downstairs **running a cleaning cycle** during that window. |
| Restore | Baseline `0700010007050100` + display `1380/420` + sleep `720/360` + delay `4` verified at **19:41** (`match: true`). Earlier `G_restore` once returned null readback but the write had already stuck. |

**Interpretation:** Strong **correlation** (armed near-now slots ↔ observed clean / `workstatus=1`), **not proven causation**. Confounders: sticky `handMode=1` from earlier Clean probes; clean started slightly *before* the armed minute; Exp B’s near-now arm did **not** fire. Treat schedule-fires-clean as **plausible / needs a clean-box retest** (no prior Clean that day, single future slot, watch `workstatus` + physical motion). Do **not** ship scoop UI on this alone.

#### Activity-stream hypothesis — **falsified for Clean and Pack**

Hypothesis: blob is a packed log of cleans / visits / errors / seals.  
**Result:** neither Clean nor Pack appended or retimestamped the field. Combined with successful arbitrary HH:MM writes and no fire-at-slot in Exp B, the **schedule-slot** model remains strongest (config, not activity ring buffer). Exp F did not change that — the blob stayed the armed schedule while a clean ran.

#### HA stance

Still **unused by HA clocks**. Optional future “scheduled scoop” UI only after a cleaner causation retest (see Exp F/G). Do not treat as activity history.

#### Captures

- Historical: Downstairs=`0700010007050100`, Upstairs=`00`
- Live experiments: [`captures/shovel_schedule_experiments_2026-08-22.jsonl`](captures/shovel_schedule_experiments_2026-08-22.jsonl) (no secrets)

### 5.0c Property update times (`{value, time}`)

`properties/get` often returns each key as `{ "value": …, "time": … }`.

- `time` is typically **milliseconds** since epoch (seal captures: e.g. `1786937055000`).
- HA **must preserve** these (1.3.22+: `device["property_times"]` as unix seconds). Flattening values-only loses clean/pack/error clocks.
- Useful edges:
  - **Last clean:** `completionStatus` time when finished (`1`), and/or `workstatus` time on 1→0
  - **Seal/pack:** `handMode` / `workstatus` time when packing (`3`)
  - **Bag / No Bag / full clear:** `errorReportEvent` time on bit clear

Apply cloud times only when an edge is detected this poll; ignore absurd future/ancient stamps (`device_time.sane_event_ts`).

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
| **Always on** (force lit) | `DisplaySwitch = 0`. **Stays lit overnight** with no button (Downstairs; owner next day). Not a timeout/wake mode. |
| **Scheduled blanking** | `DisplaySwitch = 1` + `displayStartTime` / `displayEndTime` (minutes from midnight). Inside window → blank. **Outside the window does not auto-light** (Downstairs 2026-08-16 21:40–21:43 still dark). Any **button press wakes** the panel even while “off”; that wake is temporary. |
| **Always off** | Still not isolated. `DisplaySwitch=1` already stays dark until a button; a full-day window may be indistinguishable from that. |

#### What HA got wrong historically

- Mapped **Screen off** only to **`masterSleepOnOff`**.  
- Ignored **`DisplaySwitch`** (the bit that matched the panel).  
- Looked for non-existent `masterSleepStartTime` keys; real keys are **`displayStartTime` / `displayEndTime`**.  
- Assumed polarity “1 = screen power off” for DisplaySwitch — **opposite for force-on** (`0` = lit).

#### Apply lag

After a `DisplaySwitch` / schedule write, the **physical panel can lag under a minute** (cloud → device). HA should treat that as expected, not as a failed write. Immediate `properties/get` can still show the old value; local snapshot + next poll is the right model.

#### Timezone — GMT/UTC is **not** the Upstairs-off explanation

HA **Screen blank now** compares schedule minutes to **Home Assistant’s local timezone** (this house: `America/Los_Angeles` / PDT).

Overnight tests could not tell UTC from PDT because 23:00–07:00 overlaps both clocks. The **2026-08-16 20:08 PDT** three-box capture can:

| Box | DisplaySwitch | Window (minutes) | 20:08 PDT (min 1208) | 03:08 UTC (min 188) | You saw |
|-----|---------------|------------------|----------------------|---------------------|---------|
| Downstairs | 0 Always on | 23:00–07:00 unused | lit | lit | **On** |
| Upstairs | 1 Scheduled | 22:00–06:00 (1320–360) | **outside → should be lit** | inside → blank | **Off** |
| Master | 1 Scheduled | 07:00–23:00 (420–1380) | **inside → blank** | outside → lit | **Off** |

If every box used **UTC minutes**, Master would have been **lit** at 20:08 PDT. It was **off**. So **UTC-only is falsified** as the global rule.

Upstairs being **off outside** its 22:00–06:00 local window is therefore **not** explained by GMT. Remaining hypotheses (do not code as fact): full-bag (`errorReportEvent=32`) blanks the panel; device clock ≠ HA TZ; firmware `zvb-114` differs from Downstairs/Master `zxc-111`.

Treat schedule numbers as **house-local minutes** (this house: PDT). Narrow Eco window tests on 2026-08-16 (§5.8) **confirmed PDT** and **falsified Virginia/Eastern and UTC**.

### 5.2 `errorReportEvent` is bitwise

Values are powers of two. HA treats them as a **bit mask**, not a single exclusive enum.

| Bit | Value | Meaning (current) | Evidence |
|-----|-------|-------------------|----------|
| — | 0 | Clear / not full | Downstairs + Master live, not full |
| 4 | 16 | Litter full (documented) | Older map / decompile; **not seen live** on these boxes |
| 5 | **32** | **Litter full** | **Live Upstairs 2026-08-16** while the bag was full. Was wrongly labeled “Normal operation.” |
| 6 | 64 | **Not drawer-out.** Seen only **with 524288** during trash-door jam | Drawer physically out + “No trash box” screen: cloud stayed **0**. HA “Drawer” binary is wrong. |
| 7 | 128 | Cover open (documented) | **Falsified as lid-off.** Lid removed → **512**, not 128. |
| 7 | **128** | **No Bag** (waste bag missing / sealed bag still in way) | Live Downstairs bag-replace **2026-08-22**: baseline No Bag = **128**; cleared to **0** after new bag; then clean (`workstatus` 1 → 0, `completionStatus` 3 → 1). Capture: `captures/downstairs_no_bag_replace_watch.jsonl`. |
| 9 | **512** | **Lid / cover off** | Live lid-off. With No Bag: **640** = 128\|512 while lid removed. |
| 12 | **4096** | Seen **only while pouring litter** (~2s), then 0 | Live Upstairs 2026-08-16; **not** Needs emptying |
| 19 | **524288** | With **64** → trash-door blocked / screen **Device Failure E4** | Live Downstairs jam 2026-08-16. Not seen alone. |
| others | 1, 2, 4, 8, 256 | Sensor / motor / temp | Documented; not re-verified |

**Needs emptying** is on when `(code & 16) != 0` **or** `(code & 32) != 0`.

HA **must** walk bits above 512. Combined **524352** is **Trash door blocked** (screen **Device Failure E4**), not drawer. **Cover / lid off** is **512** (and documented **128** if it ever appears). **Drawer-out is not in the cloud** — a physical drawer pull stayed `errorReportEvent=0`.

We have **not** seen 16 and 32 set together. Both bits mean full so a combined value still works.

### 5.3 Live Upstairs seal → bag change → app clean (2026-08-16 PDT)

Physical: HA **Seal waste bag**, pull drawer, remove bag, drawer in (new bag inflated), then **app Clean**. Capture: [`captures/upstairs_seal_empty_2026-08-16.jsonl`](captures/upstairs_seal_empty_2026-08-16.jsonl). App login repeatedly returned **10403** (single session).

| Local time | errorReportEvent | handMode | workstatus | completionStatus | Notes |
|------------|------------------|----------|------------|------------------|-------|
| 20:24:21 | **32** full | **3** pack | **3** | 1 | Seal / drawer |
| 20:26:21 | **0** clear | **1** clean | **1** | **3** running | New bag up; app clean |
| 20:27:56 | **0** | **1** | **1** | **3** | Still cleaning in API |
| 20:27:58 | **0** | **1** (sticky) | **0** idle | **1** complete | **API** flipped idle (2s poll) |
| after “finished” | | | | | Owner: box **still ran a few seconds** after they called it done |

Do **not** treat a spoken “finished” as the API edge. The cloud went `workstatus=0` / `completionStatus=1` at **20:27:58**; the mechanism can keep moving a few seconds after that (same class of lag as display writes, opposite direction: **API can lead the hardware**).

Learned:

- Full **clears on bag replace** (`32` → `0`), not when clean finishes.  
- `handMode` is **last command**, not “what it is doing now.” After clean it stayed **1** while idle.  
- `workstatus` **3** = packing; **1** during clean (so **Cat inside** would have been true during a clean — do not treat 1 as cat-only); **0** when the cloud thinks the cycle is done.  
- `completionStatus` **3** = running, **1** = finished (our old “Failed” label for 3 is **wrong**).  
- Physical stop can lag the API by a few seconds.

### 5.4 Live Upstairs litter pour (2026-08-16 ~20:37 PDT)

Owner poured **5.29 lb** of litter into Upstairs. Capture: [`captures/upstairs_litter_add_2026-08-16.jsonl`](captures/upstairs_litter_add_2026-08-16.jsonl).

| Local time | workstatus | errorReportEvent | catWeight | catLitterType |
|------------|------------|------------------|-----------|---------------|
| 20:36:16 | 0 | 0 | 4020 g | 0 |
| 20:37:04 | **5** | 0 | 4020 g | 0 |
| 20:37:06 | **5** | **4096** | 4020 g | 0 |
| 20:37:08 | 0 | 0 | 4020 g | 0 |

Learned:

- Cloud does **not** record how much litter was added. **5.29 lb never appears.** `catWeight` stayed 4020 g (last visit, not bowl fill).  
- Brief **`workstatus=5` + `errorReportEvent=4096`** is the only pour signature (~2–4 s). Do not treat 4096 as full.  
- HA **I refilled the litter** is still required for Litter age / last refilled (local analytics). Pressed on Docker after this pour: age **0.0 h**, refills 30d **0 → 1**.

### 5.5 Live Upstairs on-box Litter Reset (2026-08-16 ~20:41 PDT)

Physical button on the box (rotate + spread + tare). **Not** the HA analytics button. Capture: [`captures/upstairs_litter_reset_physical_2026-08-16.jsonl`](captures/upstairs_litter_reset_physical_2026-08-16.jsonl).

| Local time | workstatus | error | completionStatus | catWeight |
|------------|------------|-------|------------------|-----------|
| 20:40:33 | 0 | 0 | 1 | 4020 g |
| 20:41:12 | **8** rotation | 0 | 1 | 4020 g |
| 20:41:14 | **8** | **4096** ~2s | 1 | 4020 g |
| 20:41:16–20:42:13 | **8** | 0 | 1 | 4020 g |
| 20:42:13 | **0** | 0 | **5** | 4020 g |
| 20:42:26 | **5** | **4096** | **5** | 4020 g |
| 20:42:31+ | **6** tail | 0 | **5** | **4020 g** |

Learned:

- Physical on-box reset is **`workstatus=8`**. The on-box button does **not** change `handMode`.  
- Cloud command **`handMode: 6`** (Master, two runs) produces the **same `workstatus=8` ~60s cycle** and **`completionStatus=5`**.  
- **`catWeight` does not change** (still last-visit grams). Tare is internal.  
- HA **I refilled the litter** still only timestamps analytics unless we wire it to `handMode: 6`.

### 5.6 Live Downstairs jammed trash door + Clean (2026-08-16 ~21:18 PDT)

Owner put a weight on the **trash-bin lid** so Clean could not open it. Then cloud **Clean only** (`handMode=1`). Capture: [`captures/downstairs_jammed_trash_door_clean_2026-08-16.jsonl`](captures/downstairs_jammed_trash_door_clean_2026-08-16.jsonl).

| Local time | handMode | workstatus | errorReportEvent | completionStatus | Notes |
|------------|----------|------------|------------------|------------------|-------|
| 21:18:18 | 6 | 0 | 0 | 5 | Baseline (sticky litter-reset) |
| 21:18:20 | **1** | **1** | **524352** = 64\|524288 | 5 | Clean accepted; **drum never moved** |
| ~21:22 | 1 | 1 | 524352 | 5 | Screen **Device Failure E4** (owner; hard to read) |
| 21:23:31 | **5** | 1 | 524352 | 5 | Cloud **Resume** `code=0` — **error stayed** |
| 21:23:52 | **1** | 1 | 524352 | 5 | Cloud **retry Clean** `code=0` — **error stayed** |
| 21:25:47 | 1 | 1 | 524352 | 5 | Still latched |
| 21:25:49 | 1 | 1 | **0** | 5 | On-box **OK/Enter**; error cleared ~2s later |
| 21:27:47 | 1 | 1 | 0 | **1** | Cloud: finishing |
| 21:27:49 | 1 | **0** | 0 | **1** | Cloud idle |
| after idle | | | | | Drum stopped; **screen spinner ~8–10s**; then checkbox **Complete** |

Learned:

- Real-world cause (owner): a **clump lands on the waste door** instead of dropping into the open bag, so the door cannot open. The lab run used a weight on the lid; the bit and E4 screen are the same.  
- Trash-door jam during Clean is **`errorReportEvent=524352`**, not old bit **4** (motor blocked).  
- Cloud **Resume** and **retry Clean** do **not** ack E4. The box stays `workstatus=1` with the bits latched until the **on-box OK/Enter**.  
- After OK, clean **continues** (`work=1`, `err=0`) and finishes like a normal clean (`comp=1`, then `work=0`).  
- HA has **no cloud write** that replaces the panel ack (do not invent `errorReportEvent=0`).  
- **API leads the panel:** cloud was idle at 21:27:49; after the drum stopped the screen still spun **~8–10s** before the checkbox / Complete. Do not treat `workstatus=0` as “the box is done showing a cycle.”

### 5.7 Live Downstairs child lock + narrow screen window (2026-08-16 ~21:33 PDT)

Capture: [`captures/downstairs_childlock_screen_2026-08-16.jsonl`](captures/downstairs_childlock_screen_2026-08-16.jsonl). Restored to Always on (`DisplaySwitch=0`, 23:00–07:00 unused).

**Child lock**

| Step | API | Owner |
|------|-----|-------|
| `childLockOnOff=1` | `code=0`, GET `1` | **Locked screen** |
| `childLockOnOff=0` | `code=0`, GET `0` | Unlocked; **menu moved** |

**Narrow schedule** (`DisplaySwitch=1`, blank 21:37–21:40 = minutes 1297–1300)

| Clock | Expected if “outside window = lit” | Observed |
|-------|-------------------------------------|----------|
| 21:36 | On (outside) | On — **after child-lock button presses** |
| ~21:36:50 | Still on until 21:37 | **Off** (~10s early) |
| 21:37–21:40 | Off | Off |
| 21:40–21:43 | On again | **Still off** (3 min past end) |
| Any button | — | Owner: screen **always wakes** on a press, even when off |

Learned:

- Cloud child lock **does** lock/unlock the panel.  
- A button **always** lights a blank panel. The 21:36 “on” was **wake**, not proof of schedule.  
- **Outside the blank window the panel did not come back on by itself.** HA **Screen blank now** is schedule *intent*, not physical pixels.  
- House-local minutes still fit (UTC 21:37 PDT would be 04:37 UTC; a UTC box would not have used 1297). The early blank is timeout/clock slop, not UTC.

### 5.8 Eco timezone windows (Downstairs, 2026-08-16 ~22:00 PDT)

Capture: [`captures/downstairs_eco_tz_windows_2026-08-17.jsonl`](captures/downstairs_eco_tz_windows_2026-08-17.jsonl). Eco = `DisplaySwitch=1`. No live “pixels on” property; only the three settings change.

| Test | Window | PDT 22:xx | Eastern 01:xx | UTC 05:xx | Panel |
|------|--------|-----------|---------------|-----------|-------|
| 1 | 21:59–22:09 | inside | outside | outside | **Off** |
| 2 | 00:00–00:05 | outside | outside | outside | **On** |
| 3 | 01:11–01:21 | outside | **inside** | outside | **Stayed on** (no button) |
| 4 | 22:13–22:22 | **inside** | outside | outside | **Off** at ~22:15, still off 22:17 |

Rule: Eco blanks **inside** `displayStartTime`–`displayEndTime`. Those minutes are **house-local (PDT)**, not Virginia/Eastern and not UTC. Restored Always on (`DisplaySwitch=0`, 23:00–07:00 unused).

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

**Fixed in 1.3.9:** `extract_pet_weight_grams` uses roster `unit` (`1` = lb on this US account) before matching. Do not treat bare `weight < 80` as kg.

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

### 8.3 What HA does for clocks (1.3.22+ / 1.4.0+)

| Concern | Cloud source | Live HA role |
|---------|--------------|--------------|
| **Last visit** | `/device/data/wc` `start_time` (prefer when rows exist) | 30s occupy→idle edges still drive Dirty/awaiting; WC↔presence dedup (1.4.0) |
| **Last cleaned** | `completionStatus` / `workstatus` **property times** on clean finish | Edge on 30s path **even without Dirty** (1.4.0 A1); stamp from edged property time |
| **Bag age** | `errorReportEvent` / `workstatus` times on seal/empty/clear; live `workstatus` 3→0 pack | Seal = new bag (HA button **and** cloud pack, 1.4.0); no sticky `handMode` fallback |
| **Litter age** | `workstatus` time on →8 | Device reset uses property time (1.4.0 A3) |
| **Day boundary** | `LocalTime` day key change | Reset WC ingest watermark for new “today” |

- Matching without Jet/Tigger on roster → wrong names; without lb unit → wrong deltas (fixed 1.3.9).  
- Empty WC after midnight must **not** wipe Last visit — only `LocalTime` day change resets the WC watermark.

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
| **Litter reset (spread/tare)** | **`handMode: 6`** | Live-verified Master; same `workstatus=8` as on-box button |
| Pause / Resume | `handMode: 4` / `5` | OK |
| **Empty** | `handMode: 2` | **Destructive — user authorize only** |
| **Pack / seal** | `handMode: 3` | **User authorize only** |
| Auto-clean / delay / child lock | FullAutoModeSwitch, catCleanOnOff, childLockOnOff | Safe config |
| Display force on | DisplaySwitch=0 | Safe; verified |
| Display scheduled mode | DisplaySwitch=1 + times | Safe; blanking in window verified at night |
| DND | disturb API | Unverified stickiness |

---

## 10.5 Box state machine (live vs clocks)

```text
                    properties/get
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
     values only                    property_times
          │                               │
          ▼                               ▼
  box_state.classify()              Last cleaned / bag
  (phase, cat, faults)             (on detected edges)
          │
          ├─ 30s presence: visit open/close, Dirty awaiting, clean-cycle edges
          │
          └─ 5min full: + WC history → Last visit (prefer start_time)
                        + LocalTime day key → WC watermark rollover
                        + wcheader daily stats
```

HA classifies each properties **values** snapshot in `box_state.classify()` once. Occupancy, **What the box is doing**, and Dirty/awaiting edges all read that result. Do not re-parse `workstatus` in a third place.

**Live phase priority:** E4 trash door → reset (8/6) → pack (3) → pour (5) → clean (`workstatus=1` and `completionStatus` 2 or 3) → best-effort cat (`workstatus=1`) → idle (`0`) → sticky `handMode` only if `workstatus` is missing.

**Clocks** (Last visit / Last cleaned / Bag age) prefer cloud WC + property `time` stamps when present (§5.0c, §8.1). Wall-clock `time.time()` is fallback when the cloud time is missing or insane.

The 5-minute full poll **does not** open visits. Presence (30s) owns those edges so a stale full snapshot cannot invent a cat.

## 11. HA UX (shipped 1.3.9+)

**Screen mode** (one select):

1. **Always on** → `DisplaySwitch=0`  
2. **Scheduled** → `DisplaySwitch=1` + `displayStartTime`/`displayEndTime`  
3. **Always off** → still TBD (daytime physical test; not a shipped option)

Keep power users’ raw attributes / events.

Do **not** map Screen off to `masterSleepOnOff`. The old switch class was removed in 1.3.10.

---

## 12. Verified vs assumed

| Topic | Status |
|-------|--------|
| DisplaySwitch 0 = lit | **Verified** (physical) |
| DisplaySwitch 0 stays lit overnight | **Verified** owner (Downstairs still on the next day; Eco off) |
| DisplaySwitch 1 + night window = dark | **Verified** (physical) |
| DisplaySwitch 1 + outside window = auto lit | **Falsified** Downstairs 21:43 PDT — stayed dark; button wakes anyway |
| masterSleepOnOff alone controls panel | **Falsified** in these tests |
| displayStart/End minutes local wall | **Likely house-local**; **UTC-only falsified** by Master off at 20:08 PDT (see §5.1) |
| errorReportEvent 32 = full | **Verified** live (Upstairs zvb-114) |
| errorReportEvent is a bitfield | **Strong** (powers of two; HA uses masks) |
| error 64 = drawer out | **Falsified** — drawer out / “No trash box” stayed 0; 64 only seen with 524288 on trash-door jam |
| error 512 = comms | **Falsified** — lid off was **512** |
| error 524352 = trash-door jam / E4 | **Verified** Downstairs 2026-08-16; cloud Resume/Clean cannot ack |
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

## 14. Retrospective — why the API was used wrongly

These mistakes shipped because we trusted **one box, one night, and an inherited code map** instead of live multi-box captures.

| What we assumed | What was true | Lesson |
|-----------------|---------------|--------|
| `errorReportEvent == 16` means full; **32 = “Normal operation”** | Full Upstairs reported **32**; not-full boxes reported **0**. 32 is full, not normal. | Never invent enum labels. Capture a **full** box before coding Needs emptying. Treat the field as a **bitfield**. |
| One Downstairs snapshot is enough | Upstairs firmware **zvb-114** vs Downstairs/Master **zxc-111**; codes and schedules differ | Always compare **all boxes** when a field is “wrong on one.” |
| Exclusive `==` is safer than bits | Combined errors (full+drawer) would miss **every** PROBLEM sensor | Use `&` masks for 16/32/64/128. |
| `masterSleepOnOff` is Screen off | Panel follows **DisplaySwitch** + schedule | Physical check beats property names. |
| Pet `weight < 80` is kg | US roster `unit=1` is **pounds** | Read the unit field. |
| Overnight 23:00–07:00 proves local vs UTC | That window is true in **both** PDT and UTC at night | Use a **daytime-only** window to prove TZ. UTC-only is already **falsified** (Master). |
| GET right after SET is truth | Cloud GET can stay stale; panel can lag **&lt; 1 min** | Optimistic local snapshot; do not snap the UI back. |
| Shared family login is fine | App looks like **one session**; HA login kicks the phone | Dedicated Furbulous account for HA. |

## 15. Open questions (for next session)

1. **Always off:** Outside the scheduled window, with DisplaySwitch=1, is the panel lit?  
2. **Narrow daytime window** to prove device clock vs HA local (do not leave it overnight).  
3. Does **error 32** (full) also blank the panel? (Best remaining explanation for Upstairs off at 20:08 PDT.)  
4. **DND:** App toggle vs `is_disturb` vs `sleepTime*`.  
5. **Cleo** weight once first visit exists.  
6. Confirm vendor **single-session** login (dedicated account).

---

## 16. Integration implementation checklist

- [x] Screen mode select: **Always on** / **Scheduled** (`DisplaySwitch`)  
- [x] Stop using masterSleepOnOff as sole “Screen off” (switch removed; mode select)  
- [x] Map schedule times to `displayStartTime`/`displayEndTime` (minutes)  
- [x] Map Quiet hours times to `sleepTimeStart`/`sleepTimeStop`  
- [x] Ingest `/device/data/wc` into analytics / Last cat / Last visit (when API returns rows — often **today-only**)  
- [x] Fix pet weight: `unit==1` → pounds → grams; normalize `nickname`/`pet_id`  
- [x] Fix HA weight display for US Customary (lb) when unit system is US  
- [x] UAT tests for screen mode + unit=1 lb matching  
- [x] Quality PROMPTS point at this doc  
- [x] Needs emptying: treat error bits **16 and 32** (live Upstairs full=32)

### WC history note (2026-08-16 ~00:00 PDT)

`GET /device/data/wc` returned **[]** after local midnight even though Aug 15 visits existed earlier the same calendar evening. Treat WC as **rolling “today” (device/cloud day boundary)**. Detect that boundary via **`LocalTime` day packing** (§5.0a): on day-key change, reset the WC ingest watermark so today’s rows can hydrate again. Do not clear Last visit merely because WC returned `[]`.

---

## 17. Capture index

| File | Content |
|------|---------|
| `captures/physical_check_display_2026-08-15.jsonl` | Step log + API echoes |
| `captures/downstairs_snapshot_redacted.json` | Properties, pets, WC visits (no secrets) |
| `captures/three_box_compare_2026-08-16.json` | Downstairs / Upstairs / Master (Upstairs full=`32`) |
| `captures/upstairs_seal_empty_2026-08-16.jsonl` | Upstairs seal + bag change + app clean |
| `captures/upstairs_litter_add_2026-08-16.jsonl` | Upstairs 5.29 lb litter pour (`workstatus=5`, error `4096`) |
| `captures/upstairs_litter_reset_physical_2026-08-16.jsonl` | On-box litter reset (`workstatus=8` → `6`, `completionStatus=5`) |
| `captures/downstairs_jammed_trash_door_clean_2026-08-16.jsonl` | Weight on trash lid + Clean → `524352` / E4; on-box OK cleared and clean finished |
| `captures/downstairs_childlock_screen_2026-08-16.jsonl` | Child lock on/off; narrow 21:37–21:40 blank; outside window stayed dark |

**End of reference.** Update date and “Verified” tables when new physical or endpoint evidence lands.
