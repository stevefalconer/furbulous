# Power user guide — events, attributes, automations

Cat-parent **names** are friendly. Power-user **contracts** stay stable:

- `unique_id` (entity registry)  
- Vendor property names in attributes (`vendor_property`)  
- Analytics `metric_key` on rollup sensors  
- Domain **bus events** for edge-triggered automations  

**Version:** 1.3.8+

### Unique IDs (cat-parent scheme)

```
furbulous_{device_id}_{slug}          # litter box
furbulous_pet_{pet_key}_{slug}        # pet roster
```

Examples: `furbulous_42_last_cat`, `furbulous_42_needs_emptying`,  
`furbulous_42_empty_waste`, `furbulous_42_bag_age_hours`.  
Full map: `custom_components/furbulous/entity_ids.py`.

---

## 1. Bus events

Fired on the HA event bus (Settings → Automations → trigger type **Event**).

| Event type | When | Useful data fields |
|------------|------|--------------------|
| `furbulous_visit_ended` | Cat left after a debounced visit | `device_id`, `iotid`, `pet_name`, `pet_id`, `weight_g`, `duration_s`, `identity_method`, `identity_confidence`, `weight_match_delta_g` |
| `furbulous_waste_full` | Waste-full edge confirmed | `device_id`, `iotid` |
| `furbulous_waste_cleared` | Full condition cleared | `device_id`, `time_full_s`, `cleared_how` |
| `furbulous_bag_replaced` | Empty completed a bag cycle | `device_id`, `lifetime_s`, `source` |
| `furbulous_pack` | Seal waste bag recorded | `device_id`, `source` |
| `furbulous_litter_reset` | “I refilled the litter” | `device_id`, `interval_s`, `source` |

All include `config_entry_id` and `domain`.

### Example automation sketch

```yaml
alias: Announce which cat used the box
trigger:
  - platform: event
    event_type: furbulous_visit_ended
condition:
  - condition: template
    value_template: "{{ trigger.event.data.pet_name not in [none, '-', ''] }}"
action:
  - service: notify.mobile_app_you
    data:
      message: "{{ trigger.event.data.pet_name }} used the litter box"
```

```yaml
alias: Bag full notification
trigger:
  - platform: event
    event_type: furbulous_waste_full
action:
  - service: notify.mobile_app_you
    data:
      message: "Litter box needs emptying"
```

---

## 2. Entity attributes (stable hooks)

Many entities expose:

| Attribute | Purpose |
|-----------|---------|
| `audience` | `primary` / `chore` / `setting` / `power` |
| `automation_hint` | Short guidance |
| `vendor_property` | Cloud property name |
| `metric_key` | Analytics metric id |
| `raw_value` / `raw_hand_mode` / `raw_completion_status` | Unmapped vendor values |
| `error_code` | Bit for PROBLEM sensors |
| `match_method`, `confidence`, `pet_id`, `weight_delta_g` | Multi-cat identity |

**Do not depend on display names** in automations — use `entity_id`, `unique_id`, or events.

---

## 3. Mapping friendly name → capability

| Friendly name | Capability |
|---------------|------------|
| Last cat | Text state = pet name; attrs for match quality |
| Last visit | `Name · local time` for logbook |
| Needs emptying | PROBLEM binary; error 16; events full/cleared |
| What the box is doing | handMode enum labels + `raw_hand_mode` |
| Clean cycle status | completionStatus labels + raw |
| Auto-clean after visits | FullAutoModeSwitch 0/1 |
| Auto-clean minutes before | catCleanOnOff (1–30) |
| Screen off start/end | masterSleepStartTime / masterSleepEndTime (or aliases); writable time entities |
| Quiet hours start/end | disturbStartTime / disturbEndTime (or aliases); writable time entities |
| Empty all litter | handMode 2 (requires Empty — confirm ready) |
| Seal waste bag | handMode 3 |
| Bag age (hours) | hours since bag_replaced |
| Litter age (hours) | hours since litter_reset |

---

## 4. Polling budget (Pi-aware)

| Path | Interval | Content |
|------|----------|---------|
| Presence | 30s | Properties only |
| Pet roster | ≤60s | Cached `pet/list` |
| Full | 5 min | List + stats + pets force + analytics recompute |

Secondary sensors stay **disabled by default** to limit recorder noise. Enable as needed.

---

## 5. Diagnostics

Device/integration → **Download diagnostics** (redacted). Useful for discovering eco/DND schedule property keys.

---

## 6. Quality gates

```bash
.venv/bin/pytest tests/quality/ -v
```

See [tests/quality/PROMPTS.md](../tests/quality/PROMPTS.md) and [ISSUES.md](../tests/quality/ISSUES.md).
