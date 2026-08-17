# Furbulous dashboard (Mushroom)

File: [`furbulous.yaml`](furbulous.yaml)

**Needs:** Furbulous **1.3.11+** running on **this** Home Assistant, then a restart. [Mushroom](https://github.com/piitaya/lovelace-mushroom) via HACS (frontend only).

## If HA lists a pile of entity IDs and refuses to save

That list is “I cannot find these entities,” not a Furbulous crash.

1. You are editing the **house** HA that already has Furbulous (same boxes: Downstairs / Upstairs / Master).  
2. **1.3.11 is installed and HA was restarted** (Trash door jammed is new).  
3. Developer tools → States → search `cat_inside`.  
   - If **nothing** matches, this HA does not have the integration loaded.  
   - If you see e.g. `binary_sensor.downstairs_litter_box_cat_inside`, copy those names into the YAML.

Do **not** import with a sections dashboard (`type: sections`). That view rejects the save when any entity is missing. This file is a normal view.

## Import

1. Settings → Dashboards → **Add dashboard** → New dashboard from scratch.  
2. Open it → pencil → ⋮ → **Raw configuration editor**.  
3. Delete the default YAML. Paste **all** of `furbulous.yaml`. Save.

## What the red waste-door chip means

A clump landed **on** the waste door. Not a visit. Scoop it off, press **OK on the box**.
