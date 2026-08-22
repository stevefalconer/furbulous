# UAT ↔ Production alignment

Updated 2026-08-22 so Docker UAT (`ha-furbulous`) mirrors production entity/area layout.

## Areas (devices assigned)
| Device | Area | Entity prefix |
|--------|------|----------------|
| Downstairs | Family Room | `family_room_downstairs_` |
| Master | Master Bedroom | `master_bedroom_master_` |
| Upstairs | Front Bedroom | `front_bedroom_upstairs_` |
| Cleo | Middle Bedroom | `cleo_` + `middle_bedroom_cleo_` for toilet/bag_status/last_cleaned/no_bag/needs_cleaning |

## Also aligned
- `configuration.yaml`: US customary, America/Los_Angeles (already matched)
- Automations: production-style entity IDs + persistent_notification
- Lovelace: `dashboard-furbulous` from production-matched JSON

## Not cloned (by design)
- Full production area list / non-Furbulous devices
- Companion `notify.mobile_app_*` (UAT uses persistent_notification)
- Production auth users / add-ons

## Verify
1. Open http://127.0.0.1:8123/dashboard-furbulous/boxes
2. Developer tools → States → `cat_inside` should show area-qualified IDs
