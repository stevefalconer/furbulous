# Furbulous dashboard (Mushroom)

File: [`furbulous.yaml`](furbulous.yaml)

**Needs:** Furbulous **1.3.11+** on this Home Assistant, then a restart. [Mushroom](https://github.com/piitaya/lovelace-mushroom) via HACS (frontend only).

## Why the first import failed

HA listed every `entity:` in the YAML because those short IDs do not exist here. Boxes live in areas, so IDs are:

| Box | Prefix |
|-----|--------|
| Downstairs | `family_room_downstairs_` |
| Upstairs | `front_bedroom_upstairs_` |
| Master | `master_bedroom_master_` |

Example: `binary_sensor.family_room_downstairs_trash_door_jammed`

Use a **new dashboard from scratch**, not a sections dashboard. Paste the whole YAML in **Raw configuration editor**.

## What the red waste-door chip means

A clump landed **on** the waste door. Not a visit. Scoop it off, press **OK on the box**.
