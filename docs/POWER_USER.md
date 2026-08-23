# Power user guide — events, attributes, automations

Cat-parent **names** are friendly. Power-user **contracts** stay stable:

- `unique_id` (entity registry)  
- Vendor property names in attributes (`vendor_property`)  
- Analytics `metric_key` on rollup sensors  
- Domain **bus events** for edge-triggered automations  

**Version:** 1.3.14+

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
| `furbulous_cleaned` | Barrel clean cycle finished | `device_id`, `pet_name`, `source` |
| `furbulous_needs_cleaning` | ≥30 min after visit, no clean | `device_id`, `pet_name`, `seconds_since_visit` |

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
| Last visit | Compact local stamp `H:MM M-D` (cat name attribute `last_cat`; primary name on **Last cat**) |
| Needs emptying | PROBLEM binary; error **16 or 32** (bitfield); events full/cleared; clear → `bag_replaced` |
| What the box is doing | handMode enum labels + `raw_hand_mode` |
| Clean cycle status | completionStatus labels + raw |
| Auto-clean after visits | FullAutoModeSwitch 0/1 |
| Auto-clean minutes before | catCleanOnOff (1–30) |
| Screen mode | DisplaySwitch 0 = always on, 1 = Eco/scheduled (blank **inside** window, house-local) |
| Screen schedule start/end | displayStartTime / displayEndTime (minutes from midnight; PDT-verified) |
| Screen is off | Schedule **intent** only — no live pixel property |
| Error message | Bitfield; 32=full, 512=lid off, 524288=trash-door E4; 64≠drawer |
| Quiet hours start/end | sleepTimeStart / sleepTimeStop (minutes from midnight) |
| Empty all litter | handMode 2 (requires Empty — confirm ready) |
| Seal waste bag | handMode 3 |
| Bag age (hours) | hours since bag_replaced |
| Litter age (hours) | hours since litter_reset |

---

## 4. Analytics persistence

Events are append-only in `config/.storage/furbulous.analytics_<entry_id>` (`STORAGE_KEY` in `analytics/store.py`). 90-day prune, 50k cap.

| Action | Store |
|--------|--------|
| HA restart / Docker recreate **with the same config volume** | Survives |
| Integration version upgrade | Survives |
| Reload entry | Survives |
| Delete config entry / wipe `.storage` / new volume | Gone |
| Reconfigure (same `entry_id`) | Survives |

Bag age restarts on **Seal**, **Empty**, waste-full clear, No Bag clear, or `furbulous.mark_bag_replaced` (cloud property times preferred when present — 1.3.22+). Litter age restarts on **I refilled the litter** (or device `workstatus=8`). **Last visit** prefers `/device/data/wc` `start_time` when the cloud returns today’s rows; **Last cleaned** prefers `completionStatus`/`workstatus` property times on clean edges. Cloud `Uses today` follows the vendor day (`LocalTime` date packing).

### Notify entities (Companion app)

| Goal | Prefer |
|------|--------|
| Bag full | `binary_sensor.<box>_needs_emptying` → `on`, or event `furbulous_waste_full` |
| Litter door E4 | `binary_sensor.<box>_trash_door_jammed` → `on` |
| Dirty (no clean 30m) | `binary_sensor.<box>_needs_cleaning` → `on`, or event `furbulous_needs_cleaning` |
| Toilet chip state | `sensor.<box>_toilet_status` (+ `severity` attr) |
| Last cleaned | `sensor.<box>_last_cleaned` |
| Any error text | `sensor.<box>_error_message` not empty / not OK |

Example YAML: [`docs/dashboards/mobile_notifications.yaml`](dashboards/mobile_notifications.yaml).

### Pause cloud polling (same account as the phone app)

| Control | Entity / service |
|---------|------------------|
| Toggle pause | `switch.furbulous_pause_cloud_polling` (ON = stop polls) |
| Pause 1 hour | `button.furbulous_pause_polling_1_hour` (auto-resume) |
| Status text | `sensor.furbulous_cloud_polling` → Active / Paused / Paused until … |
| Services | `furbulous.pause_polling` (`duration_minutes` optional), `furbulous.resume_polling` |

While paused, both the 30s presence and 5min full coordinators stop hitting the API. Turning the switch off (or waiting out a timed pause) resumes and refreshes once.

---

## 5. Polling budget (Pi-aware)

| Path | Interval | Content |
|------|----------|---------|
| Presence | 30s | Properties only |
| Pet roster | ≤60s | Cached `pet/list` |
| Full | 5 min | List + stats + pets force + analytics recompute |

Secondary sensors stay **disabled by default** to limit recorder noise. Enable as needed.

---

## 6. Diagnostics

Device/integration → **Download diagnostics** (redacted). Useful for discovering eco/DND schedule property keys.

---

## 7. Quality gates

```bash
.venv/bin/pytest tests/quality/ -v
```

See [tests/quality/PROMPTS.md](../tests/quality/PROMPTS.md) and [ISSUES.md](../tests/quality/ISSUES.md).
