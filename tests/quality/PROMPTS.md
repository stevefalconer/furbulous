# Quality suite — repeatable prompts

Use these prompts (or copy into an agent session) after each change set.
Tests live under `tests/quality/` and **must stay green** on every release.

## API truth (read before display / DND / pets / weight work)

**Mandatory:** [docs/api/FURBULOUS_API_REFERENCE.md](../../docs/api/FURBULOUS_API_REFERENCE.md)

Do **not** assume property meanings. Prefer physical checks for display.
Never Empty/Pack in discovery unless the user authorizes.

## Run all quality tiers

```bash
cd furbulous
.venv/bin/pytest tests/quality/ -v --tb=short
# Or full suite:
.venv/bin/pytest tests/ -v --tb=short
```

## Bronze (integration baseline)

**Prompt:** *Verify Bronze quality: config flow contracts, unique ids, has_entity_name, stable unique_ids, no orphan screen buttons, entity platforms load without live cloud.*

```bash
.venv/bin/pytest tests/quality/bronze/ -v
```

## Silver (runtime reliability)

**Prompt:** *Verify Silver: empty safety arm/consume, switch categories, set_property error path, orphan registry cleanup, unavailable when coordinator fails.*

```bash
.venv/bin/pytest tests/quality/silver/ -v
```

## Gold (HA entity UX)

**Prompt:** *Verify Gold: entity_category CONFIG for settings switches, Controls for Empty + Empty confirm ready, alphabetical name prefixes (7d/30d, Empty*), PROBLEM binary OK semantics, Box action labels, Eco mode start/stop sensors, disabled-by-default secondary set.*

```bash
.venv/bin/pytest tests/quality/gold/ -v
```

## Performance

**Prompt:** *Verify performance contracts: pet list throttle ≥60s, presence path no full recompute when idle, fingerprint skips unchanged state, analytics rollup only on dirty/full.*

```bash
.venv/bin/pytest tests/quality/performance/ -v
```

## UAT (user acceptance scenarios)

**Prompt:** *As a multi-cat owner: Screen mode is Always on / Scheduled; Empty requires Empty confirm ready; Full auto ≠ Pause; Last visit activity shows pet name when matched; status sensors show OK when healthy; What the box is doing follows the 30s poll.*

```bash
.venv/bin/pytest tests/quality/uat/ -v
```

## After finding a new issue

1. Add a row to `tests/quality/ISSUES.md` (status open).
2. Add a failing regression test under the matching tier.
3. Fix code until green.
4. Mark issue **resolved** with version/tag.

## Multi-role review prompt (human or agent)

```
Review this Furbulous HA change as:
1) End-user (cat parent UX on device page Controls/Config/Sensors/Activity)
2) Business analyst (chore outcomes, empty safety, multi-cat identity)
3) Developer (API honesty, unique_ids, migrations)
4) Performance developer (poll budget, Pi recorder, O-device idle path)
5) Principal developer (architecture, orphan cleanup, no fake write APIs)
6) Home Assistant expert (entity_category, PROBLEM OK, unknown vs -, disabled-by-default)
7) HA usability + general app usability (plain language, progressive disclosure)
8) Three personas: casual cat parent; multi-cat household; power automator
   — keep power events/attrs; simplify names for non-tech

Check tests in tests/quality/* and update ISSUES.md.
Verify docs/CAT_PARENT_GUIDE.md and docs/POWER_USER.md still match names.
```

## Cat-parent UAT prompt

```
As a non-technical multi-cat owner: open the device page.
Confirm you can find Last cat, Needs emptying, Bag age, Litter age,
Clean now, Empty — confirm ready, Empty waste, Auto-clean after visits
without jargon. Confirm unique_ids unchanged and furbulous_* events still fire.
```
