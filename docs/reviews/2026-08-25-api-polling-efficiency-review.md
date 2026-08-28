# API polling efficiency review — Furbulous HA integration

**Date:** 2026-08-25  
**Authors:** Principal developer (review lead) + engineering assistant  
**Status:** Recommendations only — **no code changes in this document**  
**Audience:** Development team leaders (decide options below)  
**Context:** Field report that **boxes misbehave while HA is polling** and **behave normally when cloud polling is paused**. Hypothesis: **too many cloud API calls** interfere with device/app operation (single-session / vendor rate behavior).

---

## 1. Executive summary

### Current architecture (as implemented)

| Path | Interval | Per box HTTP | Purpose |
|------|----------|--------------|---------|
| **Presence** coordinator | **30 s** | `GET properties/get` | Occupancy, Dirty edges, errors, bag chore, live dashboard |
| **Full** coordinator | **5 min** | `properties/get` + `wcheader` + `wc` | Device list refresh, daily stats, visit history, pet roster force |
| **Pets** | ≤60 s on presence; **forced** every full | `GET pet/list` (account) | Roster for name matching |
| **Writes** | On demand | `POST properties/set` (or DND PUT) | Buttons / switches / auto-clean |

**Measured idle load (happy path, no retries):**

| | 1 box | **4 boxes (this house)** |
|--|------:|--------------------------:|
| HTTP / hour | **~240** | **~708** |
| HTTP / min (avg) | ~4.0 | **~11.8** |
| `properties/get` / min / box | **2.2** | **2.2** |
| Worst minute (full + presence overlap) | ~8 | **~23 account calls**; **up to 5 device-scoped GETs/box** in that minute |

README historically quoted ~180/hour/device (presence-centric). **Actual is higher** because the 5‑minute full poll **re-fetches properties** and adds WC + wcheader.

### Constraint from leadership / product

> **Each device should have no more than 2 polls per minute.**

If “poll” = `properties/get` (the call that hits device state via the cloud):

- Presence at **30 s already uses the entire budget (2/min)**.
- The 5‑minute full path’s **extra `properties/get` violates the cap** in the overlap minute and pushes the **average to 2.2/min**.

### Field hypothesis fit

- **Pause stops both coordinators** → zero cloud GETs → matches “works when paused.”
- Vendor is known to be **single active session / sensitive to concurrent control**; continuous property polling may contend with on-box firmware or the phone app even when HA uses a dedicated account.
- We cannot prove causation from code alone; we **can** prove the call volume and where to cut without losing product features (only latency).

---

## 2. Principal developer findings

### 2.1 What must stay responsive (~30 s)

These drive the dashboard and safety UX and justify a **fast** path:

- Cat in box / visit start–end → Dirty / awaiting  
- Bag full / No Bag / E4 / lid  
- Clean / pack cycle in progress  
- Sticky bag chore (seal → remove)  
- Control confirmation after user press (local optimistic write already avoids immediate GET)

**HA best practice:** one coordinator owns the “live” resource; entities do not poll (`CoordinatorEntity`, `_attr_should_poll = False`) — **this integration already does that well**.

### 2.2 What can be slower (minutes)

- Device list membership  
- Pet roster (changes rarely)  
- WC visit history hydration (today’s rows)  
- wcheader (uses today / vs yesterday)  
- Hours-since rollups (bag age, litter age, 7d/30d) — mostly **local EventStore**, not cloud

### 2.3 Wasteful patterns (ordered by impact)

1. **Duplicate `properties/get` on every full poll** while presence already has a ≤30 s copy.  
   - Waste: **+12N calls/hour** (N = boxes) → **48/hour** at 4 boxes.  
2. **Forced `pet/list` every 5 min** despite 60 s cache on presence → **+12/hour** account.  
3. **Sequential** per-iotid awaits on full path (stretches Pi wake / overlaps presence).  
4. **WC every 5 min for every box** even when quiet (payload + HTTP; ingest is incremental but GET is not).  
5. **Resume** fires presence then full back-to-back → burst of double properties.

### 2.4 Payload notes

| Call | Payload character |
|------|-------------------|
| `properties/get` | **Full** property map every time (not field-filtered by vendor). Highest frequency. |
| `wc` | Visit array for “today”; can be empty or dozens of rows; heaviest **slow** payload. |
| `wcheader` | Tiny daily counters. |
| `device/list` | Small identity list. |
| `pet/list` | Small roster. |

**Optimization reality:** We cannot ask the vendor for a “presence-only” properties subset. Efficiency gains come from **fewer calls** and **not re-fetching** the same map, not from trimming the properties JSON.

### 2.5 Home Assistant alignment

| Practice | Status |
|----------|--------|
| Cloud I/O only in coordinators | ✅ |
| Dual fast/slow coordinators | ✅ idea; ⚠️ same resource fetched twice |
| Shared `aiohttp` session | ✅ |
| Optimistic writes without immediate GET | ✅ (vendor lag) |
| Entity fingerprinting / no spam `async_write_ha_state` | ✅ |
| Coalesce overlapping refreshes / reuse fresh data | ❌ missing |
| Bounded parallel fetch for multi-device | ❌ fully serial |
| Documented poll budget matching reality | ⚠️ README undercount |

---

## 3. Target operating model (product)

| Concern | Target latency | Max cloud pressure |
|---------|----------------|--------------------|
| Live occupancy / Dirty / bag / errors / cycle | **~30 s** | ≤ **2 `properties/get`/min/device** |
| Dashboard visit clocks (Last visit prefer WC) | **1–5 min** OK | Prefer piggyback or ≤1 WC/device/min averaged |
| Uses today / vs yesterday | **1–5 min** OK | wcheader rare |
| Controls (Clean, Seal, schedules) | **Immediate write**; UI reflects optimistically; confirm within **~30 s** next poll | Writes only on user/automation |
| Analytics rollups (7d/30d) | Local store; refresh on edge or slow poll | No extra HTTP |

---

## 4. Options for leaders (decide)

### Option A — **Budget-compliant live poll (Recommended baseline)**

**Change intent (when implemented later):**

1. Presence: keep **`properties/get` every 30 s** (exactly **2/min/device**).  
2. Full poll (**5 min**): **do not** call `properties/get` again — reuse last presence snapshot (merge device list / online flags).  
3. Full poll still fetches: `device/list` (account), `wcheader`, `wc` per device, `pet/list` **without force** if cache &lt; 5–15 min.  
4. Cap: never schedule full props fetch in a minute that already hit 2 presence props.

| | Before (4 boxes) | After (est.) |
|--|-----------------:|-------------:|
| `properties/get` / min / box | 2.2 | **2.0** |
| HTTP / hour account | ~708 | **~648** (−60 from dup props; more if pet force removed) |
| Live latency | 30 s | **30 s unchanged** |
| WC / stats latency | 5 min | **5 min unchanged** |

**Pros:** Meets **≤2 polls/min/device**; preserves 30 s dashboard live; small code change; highest ROI.  
**Cons:** Full poll’s “online” / name changes wait for list-only merge; must define staleness if presence paused mid-window.

**Decision ask:** Approve Option A as mandatory for next efficiency release?

---

### Option B — **Reduce live cadence to 60 s** (more headroom)

Presence interval **60 s** → **1 `properties/get`/min/device**, leaving budget for an occasional second props fetch or denser WC.

| | Effect |
|--|--------|
| Live Dirty / cat-in-box | **~60 s** latency (still “about a minute”) |
| Headroom under 2/min cap | **1 spare slot/min/device** |
| User hypothesis (interruptions) | Stronger relief if props/get is the stressor |

**Pros:** Clearer under vendor pressure; room for WC more often.  
**Cons:** Controls confirmation and Dirty yellow slower; may feel less “live.”

**Decision ask:** Prefer **30 s (A)** or **60 s (B)** for live properties?

---

### Option C — **Adaptive polling** (advanced)

- Idle: properties every **60–120 s**.  
- Active (occupied, cleaning, packing, bag chore, Dirty): **30 s**.  
- After user write: one coalesced refresh within 5–10 s (optional; vendor lag may make this useless).

**Pros:** Lowest average load; stays responsive when it matters.  
**Cons:** More state machine complexity; harder to test; risk of missing short edges if idle too slow.

**Decision ask:** Defer C to a later phase after A/B proven?

---

### Option D — **WC / dashboard freshness** (orthogonal to props budget)

Today WC is every **5 min**. For “Last visit” preference and Dirty correlation:

| Sub-option | Cadence | Extra load (4 boxes) |
|------------|---------|----------------------|
| D0 Status quo | 5 min | 48 WC GET/hour |
| D1 WC every **2–3 min** | Faster Last visit | ~80–120/hour |
| D2 WC only if presence saw visit end or Dirty | Event-driven | Near zero when quiet |
| D3 WC on presence path at most **1/min/device** using spare budget (only if B) | Aggressive | Uses headroom |

**Recommendation:** **D2** (event-triggered WC) or keep **D0** until props duplication is fixed. Do **not** add WC to every 30 s poll.

**wcheader:** keep on slow path; optionally every **10–15 min** (dashboard “uses today” can tolerate).

---

### Option E — **Parallelism**

`asyncio.gather` with semaphore **2–3** for per-iotid GETs on the slow path.

**Pros:** Shorter wall-clock per full tick; less overlap stretch with presence.  
**Cons:** Slightly higher instantaneous concurrency (may be **worse** for vendor interruption hypothesis).

**Decision ask:** Prefer **serial** (safer under “too many calls interrupt devices”) until A is shipped; revisit E only if Pi timeout is the problem, not device behavior.

---

### Option F — **Operational / product (no poll redesign)**

1. Default **pause while using phone app** (already exists) — document strongly.  
2. Dedicated HA Furbulous account (already recommended).  
3. Add **metrics** entities: calls/hour, last poll latency, per-endpoint counters (diagnostics) to validate the hypothesis in the field.  
4. Optional: “Eco poll” mode user switch = 60 s presence.

**Decision ask:** Ship diagnostics counters with the first efficiency PR?

---

## 5. Recommended decision package (principal developer)

| # | Recommendation | Priority |
|---|----------------|----------|
| R1 | **Adopt Option A** (reuse presence properties on full poll; stop duplicate `properties/get`) | **P0** |
| R2 | **Remove `pet/list` force** on full; rely on ≤60 s / ≤15 min cache | **P0** |
| R3 | Leaders choose **live cadence: 30 s (A) vs 60 s (B)** under the 2/min/device cap | **P0 decision** |
| R4 | WC: keep 5 min **or** move to **event-triggered (D2)**; do not put WC on 30 s path | **P1** |
| R5 | Add **poll diagnostics** (F) to prove/disprove device-interference hypothesis | **P1** |
| R6 | Defer adaptive (C) and aggressive parallel (E) until after A+R3 | **P2** |
| R7 | Update README poll budget numbers to match reality | **P1 docs** |
| R8 | Preserve pause UX; consider default tip when phone app login fails | **P2 product** |

### Functionality vs latency (honest tradeoff)

| Kept | May change |
|------|------------|
| All entities, analytics events, bag chore, auto-clean-after-drawer | Age of WC-backed Last visit if we slow WC |
| User controls still immediate writes | Live occupancy / Dirty edge detection = 30 s or 60 s by R3 |
| Local 7d/30d metrics | Full-path “hours since” refresh already local-heavy |

**No intentional feature removal** beyond accepting **higher latency** on non-live data.

---

## 6. Decision record

| Decision | Choice | Owner | Date |
|----------|--------|-------|------|
| Live `properties/get` interval | **30 s (keep)** | Leaders + principal | 2026-08-28 |
| Full poll skips duplicate props | **Yes (R1 / Option A) — approved** | Leaders + principal | 2026-08-28 |
| Pet list force on full | ☐ Remove (R2) ☐ Keep | *open* | |
| WC strategy | ☐ 5 min ☐ Event (D2) ☐ Other | *open* | |
| Parallel slow-path GETs | ☐ No until proven ☐ Semaphore 2 | *open* (recommend **No** until A ships) | |
| Diagnostics counters | ☐ Yes with first PR ☐ Later | *open* | |
| Target release | ☐ 1.5.0 efficiency ☐ Patch on 1.4.x | *open* | |

**Locked for next implementation plan:** Presence stays **30 s**; full snapshot **must not** call `properties/get` again — reuse presence data (Option A / R1). Remaining rows still need a leader tick.

---

## 7. Validation plan (after an implementation is approved)

1. **Unit:** mock API call counters for presence vs full (assert ≤2 props/min/device averaged over 5 min; assert full does not call props if presence age &lt; T).  
2. **UAT:** 4 boxes, 30–60 min idle log of HTTP counts; compare device behavior pause vs unpause.  
3. **Prod (opt-in):** diagnostics sensor `furbulous_cloud_calls_per_hour`.  
4. **Regression:** Dirty after visit, bag chore sticky, Clean/Seal buttons, pause/resume.  
5. **HA quality:** bronze/silver/gold unchanged expectations for entities.

---

## 8. Appendix — call formulas

Let \(N\) = number of boxes.

**Presence (30 s):** \(N\) × `properties/get` + \(1\) × `pet/list` per 60 s.  
**Full (5 min):** \(1\) × `device/list` + \(N\) × (`properties/get` + `wcheader` + `wc`) + \(1\) × `pet/list` (forced today).

**Idle HTTP/hour ≈** \(72 + 12 + 156N\) with current code.  
**With R1 (no full props):** ≈ \(72 + 12 + 144N\).  
**With R1+R2 (pets not forced):** ≈ \(60 + 12 + 144N\).

---

## 9. Sign-off

| Role | Statement |
|------|-----------|
| **Principal developer** | Current dual-coordinator design is sound HA architecture but **over-polls the same device resource**. Meeting **≤2 polls/min/device** requires stopping full-path `properties/get` duplication and choosing 30 s vs 60 s live cadence. Field “pause fixes devices” is consistent with this load profile; implement R1–R3 first, measure, then consider WC/adaptive. |
| **Engineering assistant** | Numbers derived from `coordinator.py`, `furbulous_api.py`, `const.py` (30 s / 5 min / 60 s pets). No code was modified for this review. |

**Next step:** Leaders complete §6 decision table; then open an implementation plan (separate from this review) for the chosen options only.
