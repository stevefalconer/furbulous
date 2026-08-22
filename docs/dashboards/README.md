# Furbulous dashboard (example)

[`furbulous.yaml`](furbulous.yaml) is an **example** built for **one house** (four Furbulous boxes). It is not a universal import that works unchanged on every install.

[`notifications.yaml`](notifications.yaml) is an example automation pack for iOS/Android Companion app alerts (bag full, E4 jammed, optional “no clean after visit”).

Home Assistant builds entity IDs from the **area** plus the **box name**. This file uses:

| Box (friendly name) | Entity ID prefix in this example |
|---------------------|----------------------------------|
| Downstairs | `family_room_downstairs_` |
| Upstairs | `front_bedroom_upstairs_` |
| Master | `master_bedroom_master_` |
| Cleo | `cleo_` |

Example: `binary_sensor.cleo_needs_emptying`

Your prefixes will differ if the boxes are in other areas, have other names, or you renamed entities.

**Needs:** Furbulous **1.3.16+**, restart after update, [Mushroom](https://github.com/piitaya/lovelace-mushroom) (HACS frontend), and optionally [card-mod](https://github.com/thomasloven/lovelace-card-mod) for borderless status chips and equal-width columns.

**Box order in the example:** Downstairs → Master → Cleo → Upstairs.

**Cloud polling (after the boxes):** `button.furbulous_pause_polling`, `button.furbulous_pause_polling_1_hour`, `button.furbulous_resume_polling`, status on `sensor.furbulous_cloud_polling`. After updating 1.3.16, restart HA once so entity IDs are normalized. Instructions stay at the bottom of the YAML.

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
