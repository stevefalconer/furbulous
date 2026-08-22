# Furbulous dashboard (example)

[`furbulous.yaml`](furbulous.yaml) is the **full pasteable Lovelace dashboard** for **this house** (four Furbulous boxes). Sidebar name: **Furbulous**. It is not a universal import that works unchanged on every install.

[`mobile_notifications.yaml`](mobile_notifications.yaml) is the **only** notifications pack (automations, not a dashboard): bag full, **No Bag**, 15‑min chore reminder, E4, and Dirty — for all four boxes, plus account-wide events. Docker testing uses `persistent_notification`; on a phone HA swap to `notify.mobile_app_*`. Do **not** paste it into the dashboard editor.

Home Assistant builds entity IDs from the **area** plus the **box name**. This file uses:

| Box (friendly name) | Entity ID prefix in this example |
|---------------------|----------------------------------|
| Downstairs | `family_room_downstairs_` |
| Master | `master_bedroom_master_` |
| Cleo | `cleo_` (some sensors: `middle_bedroom_cleo_`) |
| Upstairs | `front_bedroom_upstairs_` |

Always confirm with **Developer tools → States** (`cat_inside`). Short names like `downstairs_` alone will show as Unknown on this install.

Example: `binary_sensor.cleo_needs_emptying`

Your prefixes will differ if the boxes are in other areas, have other names, or you renamed entities.

**Needs:** Furbulous **1.3.19+**, reload integration after update, [Mushroom](https://github.com/piitaya/lovelace-mushroom) (HACS frontend), and optionally [card-mod](https://github.com/thomasloven/lovelace-card-mod) for borderless status chips and equal-width columns.

**Box order in the example:** Downstairs → Master → Cleo → Upstairs.

**Cloud polling (after the boxes):** `switch.furbulous_pause_cloud_polling`, `button.furbulous_pause_polling_1_hour`, status on `sensor.furbulous_cloud_polling`. Use **1.3.19+** — older builds deleted the hub device on Resume’s refresh, so Pause chips never returned (Spook: unknown entity). Dashboard Pause chips use `state_not: on`. After updating, reload the Furbulous integration once.

## How to adapt it to your house

1. Developer tools → **States**. Search `cat_inside` (or `trash_door`).  
2. Copy the full entity IDs for each of your boxes.  
3. Open `furbulous.yaml` in a text editor.  
4. Replace every example prefix with yours.  
5. If you have fewer boxes, delete extra `vertical-stack` sections. If you have more, duplicate a stack.  
6. Titles on the cards are only labels.  
7. Settings → Dashboards → **new dashboard from scratch** (not a sections dashboard). Pencil → ⋮ → **Raw configuration editor** → paste → save.

If a card says *Entity not available*, the ID in the YAML does not match States.

## Status vs Actions (mobile UX)

| Zone | Meaning | Color |
|------|---------|--------|
| Header | **Last/current cat · visit time** (once — not repeated). Litter/Bag age + **Last cleaned** | Red header if bag full / Dirty / litter-door error |
| Chips | Bag OK · **No errors** / **Litter door error** · **Toilet** | Toilet: green Idle/in-use · orange &lt;30m waiting · red **Dirty** |
| **Actions** | **Buttons** — Clean now, Seal bag, Refilled | Tap to run |

**Toilet status** (`sensor.*_toilet_status`): Idle after a barrel clean; pet name while occupied or waiting &lt;30m; **Dirty** at ≥30m with no clean. Automate on `binary_sensor.*_needs_cleaning` or event `furbulous_needs_cleaning`.

## What the waste-door chip means

**Trash door jammed** is not a cat visit. A clump landed **on** the waste door. Scoop it off, press **OK on the box** (HA Clean / Resume will not clear it).
