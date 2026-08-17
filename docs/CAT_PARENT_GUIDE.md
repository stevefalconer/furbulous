# Cat parent guide — Furbulous in Home Assistant

Plain-language guide for multi-cat households, “crazy cat ladies,” and cat daddies.  
You do **not** need to be a Home Assistant expert to use the everyday pieces.

**Integration version:** 1.3.11

**Sign-in tip:** Use a **separate Furbulous account** for Home Assistant. The phone app seems to allow only **one login at a time**, so using the same email as your daily app can keep kicking you out of the app.

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
- **Auto-clean minutes before** — wait time after a visit before cleaning starts.

### Empty / seal the waste

1. Close the litter drum / globe.  
2. Turn **ON** **Empty — confirm ready**.  
3. Within **90 seconds**, press **Empty all litter**.  
4. Or use **Seal waste bag** when you only want to pack/seal (no full dump).

### After you add litter

After you pour litter, press **I refilled the litter**. The box **rotates to spread it and resets the scale** (so a pile is not a cat). Litter age also restarts.

---

## 5. Configuration (set and forget)

| Name | Plain English |
|------|----------------|
| **Auto-clean after visits** | Box cleans itself after each use |
| **Auto-clean minutes before** | Wait after a visit before auto-clean starts |
| **Quiet hours** | Soft/no cleaning while quiet mode is on |
| **Quiet hours start** / **Quiet hours end** | Daily window for quiet mode (set both) |
| **Screen mode** | **Always on** = stays lit (even overnight) · **Scheduled** = Eco; blanks **during** the daily window |
| **Screen schedule start** / **Screen schedule end** | When Scheduled is on, the panel is forced off **between** these house-local times. A button still wakes it. |
| **Child lock** | Locks the physical buttons (cloud on/off works) |

---

## 6. “OK” and “Problem” (don’t panic)

Some sensors use Home Assistant’s **problem** style:

- **OK** → good news, nothing to do  
- **Problem** → needs your attention  

Examples:

- **Needs emptying** → Problem means empty/seal soon  
- **Cover open** → Problem means the **lid is off**  
- **Drawer out of place** → stays OK; the cloud does **not** tell HA when the drawer is out. Look at the box.  
- **Trash door jammed** → Problem means the waste door could not open (on-box **Device Failure E4**). Clear the lid and press OK on the box.  

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

## 9. What resets bag age, litter age, and visit history

These live in Home Assistant’s own file (not on the box): `.storage/furbulous.analytics_<config_entry_id>`.

| What you do | Bag age / Litter age | Visit / clean / pack history (90 days) |
|-------------|----------------------|----------------------------------------|
| Restart HA or the Docker container (same config folder) | **Kept** | **Kept** |
| Update the integration version (same config) | **Kept** | **Kept** |
| Reload the Furbulous integration | **Kept** | **Kept** |
| Press **I refilled the litter** | Litter age restarts | Litter-reset event added |
| Press **Empty all litter** (after confirm) | Bag age restarts | Bag-replaced event added |
| Press **Seal waste bag** | Bag age **not** restarted (pack event only) | Pack event added |
| **Delete** the Furbulous integration / config entry | **Lost** | **Lost** |
| New HA config / wipe `.storage` / new Docker volume | **Lost** | **Lost** |
| Reconfigure (same entry) | **Kept** unless the entry is replaced | **Kept** |

Cloud **Uses today** is from the Furbulous servers and can reset at their day boundary (not HA restart).

**Cat inside** is *right now* on the 30s poll. A **running clean** (`completionStatus=3`) and a **jammed trash door (E4)** are not counted as a cat, even though the box still uses `workstatus=1`. Other `workstatus=1` moments can still look like a visit — that is a vendor limit.

---

## 10. First-week checklist

1. Install via HACS → restart HA.  
2. Add Furbulous with a **dedicated** Furbulous account (not your daily phone login).  
3. Confirm **unit system** (US → lb, metric → kg).  
4. Set **pet weights in the app**.  
5. Glance **Last cat**, **Needs emptying**, **Bag age**, **Litter age**.  
6. Practice **Empty — confirm ready** + **Empty all litter** once carefully.  

---

## 11. Want more power?

Entity unique IDs stay stable when we improve names. Advanced automations, bus events, and raw codes are documented in [POWER_USER.md](POWER_USER.md). You can ignore that file forever and still use everything above.
