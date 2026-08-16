# Cat parent guide — Furbulous in Home Assistant

Plain-language guide for multi-cat households, “crazy cat ladies,” and cat daddies.  
You do **not** need to be a Home Assistant expert to use the everyday pieces.

**Integration version:** 1.3.6+

---

## 1. What you get in one sentence

See **which cat** used the box, whether it **needs emptying**, how old the **bag** and **litter** are, and press simple buttons to **clean**, **seal the bag**, or **empty** — with a safety step so empty is hard to do by accident.

---

## 2. Open the litter box device

Settings → Devices & Services → **Furbulous** → your litter box.

You’ll see sections roughly like:

| Section | What it’s for (cat language) |
|---------|------------------------------|
| **Controls** | Things you *do*: clean, empty, seal bag, refill marker |
| **Configuration** | Preferences: auto-clean, quiet hours, screen, child lock |
| **Sensors** | What’s going on with cats, bag, litter |
| **Diagnostic** | Techy details (safe to ignore) |

---

## 3. Everyday glance (most important)

| Name on screen | What it means |
|----------------|---------------|
| **Cat inside** | Someone is in the box *right now* |
| **Who is inside** | Name while occupied (else `-`) |
| **Last cat** | Who finished the last visit |
| **Last visit** | `Luna · 2026-08-15 14:32` — great for Activity history |
| **Needs emptying** | **OK** = fine · **Problem** = time to empty/seal |
| **Cat weight** | Latest weight (lb or kg from HA settings) |
| **Uses today** | How many uses the cloud counted today |
| **Bag age (hours)** | How long since you last emptied (bag change) |
| **Litter age (hours)** | How long since you marked a litter refill |

**Tip:** After install, set **accurate weights for every cat in the Furbulous app**. That’s how multi-cat matching works.

---

## 4. Chores (Controls)

### Clean the litter bed

- **Clean now** — run a clean cycle once.  
- **Auto-clean after visits** (Configuration) — ON means the box cleans itself after visits.  
- **Pause cleaning** / **Resume cleaning** — only for a cycle *already running*.  
- **Minutes before auto-clean** — wait time after a visit before cleaning starts.

### Empty / seal the waste

1. Close the litter drum / globe.  
2. Turn **ON** **Empty — confirm ready**.  
3. Within **90 seconds**, press **Empty waste**.  
4. Or use **Seal waste bag** when you only want to pack/seal (no full dump).

### After you add litter

Press **I refilled the litter** so “Litter age” restarts. The cloud may not detect refills by itself.

---

## 5. Configuration (set and forget)

| Name | Plain English |
|------|----------------|
| **Auto-clean after visits** | Box cleans itself after each use |
| **Quiet hours** | Soft/no cleaning while quiet mode is on (schedule often in the **app**) |
| **Screen off** | ON = dim/blank the display · OFF = normal |
| **Child lock** | Locks the physical controls |
| **Screen-off schedule starts/ends** | Shown when the cloud sends times; set schedule in the **app** if blank |

---

## 6. “OK” and “Problem” (don’t panic)

Some sensors use Home Assistant’s **problem** style:

- **OK** → good news, nothing to do  
- **Problem** → needs your attention  

Examples:

- **Needs emptying** → Problem means empty/seal soon  
- **Cover open** → Problem means close the cover  
- **Drawer out of place** → Problem means push the drawer in  

---

## 7. Blank values (`-` or unknown)

| You see | Meaning |
|---------|---------|
| **`-`** | No text answer yet (e.g. no last cat identified) |
| **0** | Count is zero (no visits/bags yet) |
| **unknown** | A number/time/weight isn’t available yet (normal until first data) |

---

## 8. Multi-cat homes

- Each box has its own **Last cat** / **Last visit**.  
- Matching is **closest weight** (like the app).  
- Cats with similar weights may show lower confidence (see attributes on **Last cat**).  

---

## 9. First-week checklist

1. Install via HACS → restart HA.  
2. Add Furbulous with the **same email/password/region** as the app.  
3. Confirm **unit system** (US → lb, metric → kg).  
4. Set **pet weights in the app**.  
5. Glance **Last cat**, **Needs emptying**, **Bag age**, **Litter age**.  
6. Practice **Empty — confirm ready** + **Empty waste** once carefully.  

---

## 10. Want more power?

Entity unique IDs stay stable when we improve names. Advanced automations, bus events, and raw codes are documented in [POWER_USER.md](POWER_USER.md). You can ignore that file forever and still use everything above.
