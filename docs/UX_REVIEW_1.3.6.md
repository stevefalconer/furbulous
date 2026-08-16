# UX multi-perspective review — 1.3.6

## Personas

### A — Non-technical cat parent (single or multi-cat)

**Goals:** Is anyone in the box? Which cat? Do I empty? Bag/litter stale?  
**Pain (1.3.5):** Jargon (`7d`, hand mode, Full auto), chore vs setting confusion, power sensors as noise.  
**1.3.6:** Plain names (Last cat, Needs emptying, Clean now, Auto-clean after visits), Controls vs Configuration, calm disabled defaults, [CAT_PARENT_GUIDE.md](CAT_PARENT_GUIDE.md).

### B — Multi-cat household / “crazy cat lady/daddy”

**Goals:** Per-cat identity across boxes, bag life with many cats, litter cadence, Activity with names.  
**1.3.6:** Last visit with pet name, weight match attrs retained, Bag age / Litter age primary, visits (7/30 days) wording, events for optional notify.

### C — Power user / automation hobbyist

**Goals:** Triggers on visit/full/empty without fragile name strings.  
**1.3.6:** Bus events (`furbulous_visit_ended`, …), attributes (`metric_key`, `vendor_property`, raw codes), stable unique_ids, [POWER_USER.md](POWER_USER.md). **No capability removed.**

---

## Expert lenses

### Home Assistant usability

| Principle | Application |
|-----------|-------------|
| entity_category | Settings → CONFIG; chores → Controls |
| PROBLEM class | Named conditions; OK = healthy |
| Friendly names via translation_key | has_entity_name; renames don’t break unique_id |
| Disabled by default | Secondary/power sensors |
| Device class honesty | unknown for empty WEIGHT/DURATION/TIMESTAMP |

### General application usability

| Principle | Application |
|-----------|-------------|
| Speak user language | Cat/chore words, not vendor handMode |
| Progressive disclosure | Guide first; power docs second |
| Safety for destructive | Empty — confirm ready (90s) |
| Feedback | plain_english attributes on key entities |

### Business analyst

| Outcome | Entity / event |
|---------|----------------|
| Visit identity | Last cat, Last visit, visit_ended event |
| Emptying SLA | Needs emptying, Waiting with full bag, waste events |
| Bag lifecycle | Bag age, Bag last changed, bag_replaced event |
| Litter lifecycle | Litter age, I refilled the litter, litter_reset event |
| Auto policy | Auto-clean after visits ≠ Pause |

---

## Naming principles (adopted)

1. **Primary state = cat language.**  
2. **Power data = attributes + events + unique_id.**  
3. **Group by word** (Visits…, Bag…, Litter…, Empty…).  
4. **Never rename unique_id** for cosmetic renames.  
5. **Destructive actions** pair safety + action names (`Empty —` / `Empty waste`).

---

## Recommendations implemented in 1.3.6

| # | Recommendation | Status |
|---|----------------|--------|
| R1 | Plain-language entity names | Done |
| R2 | Empty waste + Empty — confirm ready | Done |
| R3 | Auto-clean after visits naming | Done |
| R4 | Needs emptying / Cover open / Drawer out of place | Done |
| R5 | Last cat / Last visit / Who is inside | Done |
| R6 | Bag age / Litter age / I refilled the litter | Done |
| R7 | Bus events for visit/full/bag/litter | Done |
| R8 | audience + automation_hint attributes | Done |
| R9 | Cat parent + power user docs | Done |
| R10 | Quality suite UAT for naming + events | Done |

## Future (not blocking)

| # | Idea | Notes |
|---|------|-------|
| F1 | Lovelace starter dashboard YAML | Optional pack in docs |
| F2 | Writable eco times when keys confirmed | Needs field capture |
| F3 | Community translations for new English names | en first; packs reset to en this release |
