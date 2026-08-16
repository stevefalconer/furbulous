# Full testing & multi-lens review — 2026-08-16

**Scope:** Downstairs live + full automated suite + principal/HA/perf review  
**Code:** 1.3.9 WIP (uncommitted) on local Docker HA  
**Constraint:** No Empty / Pack  

---

## 1. Interactive (user-required)

| ID | Test | Status | Result |
|----|------|--------|--------|
| **I1** | Always on → panel **lit** | **YOU** | HA + API set **Always on**. Confirm panel lit. |
| **I2** | Scheduled (in night window) → **dark** | Prior session ✅ | Verified earlier with re-apply |
| **I3** | Always on after schedule → **lit** | Prior session ✅ | Verified |
| **I4** | Cat weight US lb | ✅ Automated live | **23.82 lb** (not 10.8 kg) |
| **I5** | Last cat from activity | ⚠️ Gap | WC returned **0 rows** for “today”; needs a real visit |
| **I6** | Clean now | ⏸ Optional | Not run (optional) |
| **I7** | Empty confirm arm only | ✅ | HA switch on→off works (no Empty) |
| **I8** | Child lock | ⚠️ | **API** on/off works; HA entity lagged off until refresh |

**Please reply for I1 only:** is Downstairs screen **lit** right now? (Always on is set.)

---

## 2. Automated tests

| Suite | Result |
|-------|--------|
| `pytest tests/` | **146 passed** |
| `pytest tests/quality/` (bronze/silver/gold/perf/uat) | **42 passed** |

---

## 3. Multi-lens code review (principal + HA + performance)

### Critical (fixed during this pass)

| Issue | Fix |
|-------|-----|
| WC `visit_ended` double-count / restart re-ingest | Dedup by timestamp + restore watermark from store; skip known ts |
| Orphan Screen off **switch** not pruned | Registry prune now includes **switch** `*_screen_off` |

### High (open / accepted risk)

| Issue | Recommendation |
|-------|----------------|
| +1 HTTP `/device/data/wc` per box per 5 min | Accept for 1–3 boxes; later gather/strip payload |
| Dead `FurbulousEnergySavingSwitch` class still in `switch.py` | Delete in cleanup commit |
| API doc §5/7/11 slightly stale | Update in same release |
| Child lock HA UI lag | Ensure refresh after set (API OK) |

### Solid

- DisplaySwitch model + Screen mode select  
- Pet `unit=1` → lb  
- US Customary weight display  
- Dual coordinator poll budget still sound  
- Empty safety unit-tested  

### Bronze / Silver / Gold (1.3.9 WIP)

| Tier | Verdict |
|------|---------|
| **Bronze** | **PASS** (unique ids, naming, poll structure) |
| **Silver** | **PASS** after orphan switch prune |
| **Gold lean** | **CONDITIONAL PASS** — analytics dedup addressed; option i18n for Screen mode still English-only |

---

## 4. Live entity baseline (Downstairs ~00:34–00:36 PDT)

| Entity | State |
|--------|--------|
| Screen mode | Always on |
| Screen schedule | 23:00 – 07:00 |
| Quiet hours times | 12:00 – 06:00 |
| Cat weight | **23.82 lb** |
| Last cat / last visit | `-` (no WC rows today) |
| Uses today | 0 |
| Auto-clean | on, 4 min delay |
| Needs emptying | off |
| What box is doing | Resuming (sticky handMode=5 — known oddity) |

---

## 5. Not tested (still)

- Empty / Pack (hardware)  
- Clean now / Pause / Resume physical cycle  
- Quiet hours silencing cleaning  
- Upstairs / Master physical  
- EU/Asia  
- HACS upgrade path from published 1.3.8  

---

## 6. Sign-off summary

| Role | Result |
|------|--------|
| User interactive | **Awaiting I1 lit confirm**; prior screen UAT strong |
| Automated unit + quality | **PASS 146 / 42** |
| Performance review | **PASS with +wc HTTP note** |
| HA guidelines | **PASS** with orphan prune fix |
| Principal developer | **PASS after WC dedup + switch orphan** — ship only after commit |
| Crazy cat parent | **Partial** — weight/screen good; Last cat needs a visit day |

**Release:** Do not tag until I1 confirmed + commit 1.3.9.  
