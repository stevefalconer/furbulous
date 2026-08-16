# User feedback review — 1.3.5

Multi-role answers for field feedback on Controls / Sensors / Activity.

## Controls: duplicate Screen off

**Cause:** 1.3.2–1.3.3 added Screen on/off **buttons**; 1.3.4 replaced them with a **Screen off** switch, but registry entries for the buttons could remain. A diagnostic binary also mirrored the same property.

**Fix (1.3.5):** Setup prunes `*_screen_on` / `*_screen_off` button entities. Only the **Screen off** switch remains enabled. Diagnostic mirror is **disabled by default**.

**Semantics:** Switch **ON** = screen off/dimmed; **OFF** = screen on.

## Eco mode start / stop

**Fields added:** **Eco mode start** and **Eco mode stop** under Configuration (read-only text, `HH:MM` when the API exposes known property keys).

**Write path:** Still the **Furbulous app**. We do not POST guessed property keys (principal / safety). Capture property dumps via diagnostics if you see times in the app but `-` in HA so we can map keys.

## Full auto vs Pause / Resume

| | Full auto mode | Pause / Resume |
|--|----------------|----------------|
| Role | Ongoing **policy** | **Momentary** cycle control |
| Effect | Auto-clean after visits | Stop / continue current cycle only |

## Empty + Empty confirm ready

Renamed confirm switch to **Empty confirm ready** so it sorts next to **Empty**. Both stay under **Controls** (chores). Settings moved to **Configuration**.

## Activity + pet names

New **Last visit activity** sensor: `Luna · 2026-08-15 14:32`. State changes show in the device Activity/Logbook. **Last visitor** remains the pure name sensor.

## Sensors show Unknown

| Type | Display | Option |
|------|---------|--------|
| Text | `-` | Preferred for cat-facing blanks |
| Counts | `0` | Prefer over unknown |
| Weight / duration / timestamp | HA **unknown** | Required by device classes; cannot use `-` |

## Status sensors (OK)

PROBLEM class: **OK** = healthy, **Problem** = needs attention. Renamed to *status* so OK reads naturally. See README table (codes 16 / 64 / 128).

## ~11 disabled sensors

**Expected** (Gold / Pi). Secondary rollups and day-over-day start disabled. Enable as needed.

## Hand mode

Renamed **Box action** with Idle / Cleaning / Emptying / Packing bag / Paused / Resuming.

## Cycle completion

Vendor `completionStatus` — mapped best-effort; use **raw_completion_status** attribute for automations until your unit’s enum is confirmed.

## Configuration vs Controls (1.3.5)

**Configuration:** Screen off, Full auto, DND, Child lock, Cleaning delay, Eco start/stop.  
**Controls:** Empty confirm ready, Empty, Manual clean, Pause, Resume, Pack, Mark litter reset.

## Tests

See `tests/quality/` — bronze, silver, gold, performance, UAT — plus `PROMPTS.md` / `ISSUES.md`.
