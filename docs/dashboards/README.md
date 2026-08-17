# Furbulous dashboard (example)

[`furbulous.yaml`](furbulous.yaml) is an **example** built for **one house** (three Furbulous boxes already in Home Assistant). It is not a universal import that works unchanged on every install.

Home Assistant builds entity IDs from the **area** plus the **box name**. This file uses the IDs from that house:

| Box (friendly name) | Entity ID prefix in this example |
|---------------------|----------------------------------|
| Downstairs | `family_room_downstairs_` |
| Upstairs | `front_bedroom_upstairs_` |
| Master | `master_bedroom_master_` |

Example: `binary_sensor.family_room_downstairs_trash_door_jammed`

Your prefixes will differ if the boxes are in other areas, have other names, or you renamed entities.

**Needs:** Furbulous **1.3.11+**, restart after update, and [Mushroom](https://github.com/piitaya/lovelace-mushroom) (HACS frontend). Mushroom is not a Python dependency.

## How to adapt it to your house

1. Developer tools → **States**. Search `cat_inside` (or `trash_door`).  
2. Copy the full entity IDs for each of your boxes, for example:
   - `binary_sensor.kitchen_litter_cat_inside`
   - `sensor.kitchen_litter_last_visit`
   - `button.kitchen_litter_clean_now`  
3. Open `furbulous.yaml` in a text editor.  
4. Replace every example prefix with yours:
   - `family_room_downstairs_` → your first box prefix  
   - `front_bedroom_upstairs_` → your second box  
   - `master_bedroom_master_` → your third box  
5. If you have one or two boxes, delete the extra `vertical-stack` sections. If you have four, duplicate a stack and point it at the fourth prefix.  
6. Titles on the cards (`Downstairs`, `Upstairs`, `Master`) are only labels — change them to whatever you call the boxes.  
7. Settings → Dashboards → **new dashboard from scratch** (not a sections dashboard). Pencil → ⋮ → **Raw configuration editor** → paste the edited YAML → save.

If a card says *Entity not available*, the ID in the YAML does not match States. Fix that one string; you do not need to reinstall Furbulous.

A sections dashboard (`type: sections`) may refuse to save and dump every entity ID. This example is a normal view so a missing card stays “unavailable” instead of blocking the import.

## What the waste-door chip means

**Trash door jammed** is not a cat visit. A clump landed **on** the waste door. Scoop it off, press **OK on the box** (HA Clean / Resume will not clear it).
