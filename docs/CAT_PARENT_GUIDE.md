# Cat parent guide — Furbulous in Home Assistant

Plain-language guide for multi-cat households, “crazy cat ladies,” and cat daddies.  
You do **not** need to be a Home Assistant expert to use the everyday pieces.

**Integration version:** 1.3.13

**Sign-in tip (required recommendation):** Use a **dedicated Furbulous account** for this Home Assistant integration — not the same login you use daily in the phone app. The vendor app behaves like a **single active session**: HA polling with your everyday account can disrupt the app (and vice versa).

**Pets:** Keep every cat on **that same account**. Pets that only appear because another account *shared* them with you are **not tested / not verified** with this integration (they may show in the app but not match correctly in HA).

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
| **Last cat** | Who finished the last visit (put this at the top of dashboards) |
| **Last visit** | Compact time only: `21:57 8-17` (pair with **Last cat** on dashboards) |
| **Toilet status** | **Idle** after a barrel clean · pet name while in use or waiting · **Dirty** if 30+ minutes after a visit with no clean |
| **Needs cleaning** | **Problem** when Toilet status is Dirty (good for phone alerts) |
| **Last cleaned** | When the barrel last finished cleaning, and which cat that was for |
| **Needs emptying** | **OK** = fine · **Problem** = time to empty/seal |
| **Trash door jammed** | **Problem** = waste/**litter door** jammed (E4) — not the pull-out drawer. Scoop clump, **OK on the box** |
| **Cat weight** | Latest weight (lb or kg from HA settings) |
| **Uses today** | How many uses the cloud counted today |
| **Bag age (hours)** | How long since the **bag-full error cleared** (usual after you remove the sealed bag / drawer) or since **Empty all litter** |
| **Litter age (hours)** | How long since you pressed **I refilled the litter** (or on-box litter reset). **Unknown** until the first mark |

**Tip:** After install, set **accurate weights for every cat in the Furbulous app**. That’s how multi-cat matching works.

---

## 4. Chores (Controls)

### Clean the litter bed (**Clean** = barrel moved)

- **Clean now** — run a **barrel clean cycle** once (not the same as removing the bag).  
- **Auto-clean after visits** (Configuration) — ON means the box cleans itself after visits.  
- **Pause cleaning** / **Resume cleaning** — only for a cycle *already running*.  
- **Auto-clean minutes before** — wait time after a visit before cleaning starts.

### Seal bag vs emptied bag vs Bag age

| Action | What it does | Bag age |
|--------|----------------|---------|
| **Seal waste bag** | Packs/seals the waste on the box | Does **not** restart by itself |
| Remove sealed bag + put drawer back | Clears the box “full” error in the cloud | **Restarts** Bag age when **Needs emptying** goes back to OK |
| **Empty all litter** | Dumps **all** litter (safety confirm required) | Also restarts Bag age |

If the box stays full / errored, it often **will not clean** after visits — that is why phone alerts on **Needs emptying** and **Trash door jammed** matter.

### After you add litter

After you pour litter, press **I refilled the litter** in HA (or use the on-box litter reset). The box **rotates to spread it and resets the scale** (so a pile is not a cat). **Litter age** restarts. If you only pour litter and never mark it, Litter age stays **Unknown**.

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
- **Trash door jammed** → Problem means a **clump landed on the waste door** so it cannot open. This is **not** a cat visit and **not** “the drawer is out.”

### How to clear **Trash door jammed**

This happens during a clean when waste drops a moment late and sits **on** the bin door instead of **in** the bag. The box screen often says **Device Failure E4**. Home Assistant cannot press OK for you.

1. Open the waste area and **scoop the litter off the door**.  
2. On the box, press **OK** (not a Home Assistant Clean or Resume — those will not clear E4).  
3. The clean should continue. **Trash door jammed** goes back to OK.

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
| Press **Seal waste bag** | Bag age **not** restarted yet (pack event only) | Pack event added |
| **Needs emptying** returns to OK (full error cleared in cloud) | Bag age restarts | Bag-replaced event added |
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

An **example** Mushroom dashboard (one house’s entity IDs) is in [dashboards/](dashboards/README.md). Copy it, then replace the prefixes with the IDs from **Developer tools → States** on your HA.
