# Furbulous dashboard (Mushroom)

Import [`furbulous.yaml`](furbulous.yaml) after **1.3.11** is running.

**Needs:** [Mushroom](https://github.com/piitaya/lovelace-mushroom) (HACS → Frontend). Not a Python dependency.

## Import

1. Update Furbulous and **restart** Home Assistant.  
2. Confirm entities exist: **Trash door jammed** on each box.  
3. Settings → Dashboards → **Add dashboard** → empty.  
4. Open it → pencil → ⋮ → **Raw configuration editor**.  
5. Replace the YAML with `furbulous.yaml`.  
6. If a card is unknown, the entity_id may differ. Developer tools → States → search `trash_door` and fix the names in the YAML.

This house uses **Downstairs / Upstairs / Master**. HA usually creates:

`binary_sensor.downstairs_trash_door_jammed`

If you see `…_trash_door_blocked` instead, rename those three entities in the YAML.

## What the red banner means

**Trash door jammed** is only the waste-door fault (clump on the lid, on-box E4). It is **not** shown after a normal visit. Clear the door, press **OK on the box**.
