# Correction of Errors — Private LAN IP in dashboard documentation

| Field | Value |
|-------|--------|
| **Date** | 2026-08-22 |
| **Severity** | Medium (information disclosure — private network location) |
| **Status** | Corrected at tip of `main`; **git history rewritten** to replace private LAN IPv4 → `<HA_HOST>` across commits (force-pushed) |
| **Maintainer** | Process owner for this CoE |
| **Security reviewer** | Required sign-off on this CoE before next tag |
| **Architecture reviewer** | Process acknowledgment |

## Summary

Example dashboard documentation in `docs/dashboards/furbulous.yaml` included a
**private LAN IPv4 address** identifying a household Home Assistant host. That
is a poor practice for a public HACS repository: it leaks network topology and
can aid targeting even when no password is present.

No Home Assistant or Furbulous **passwords or tokens** were found in the
tracked public tree during the remediation pass. Local UAT side-files outside
the public repo that contained an email were redacted on disk.

## Root cause

Operational notes for a single house were copied into the shared example YAML
header instead of using placeholders. There was no automated secrets scan in
the release path.

## Blast radius

- **Public GitHub history** previously contained the IPv4 string in
  `docs/dashboards/furbulous.yaml` comments (purged via history rewrite).
- **HACS / clone consumers** who pulled those commits could see the address.
- **Live HA Lovelace storage** (UI dashboard) did not require that comment for
  function; risk was primarily documentation/source control.

## Immediate correction (deploy first)

1. Removed the LAN IP and direct HA URL from `docs/dashboards/furbulous.yaml`.
2. Removed loopback HA URLs from `docs/UAT_ALIGNMENT.md`.
3. Added `docs/SECURITY_REVIEW.md` (initial + every deployment gate).
4. Added `scripts/secrets_scan.py` (fails on private IPs / obvious tokens).
5. Rewrote git history and force-pushed `main` + tags so the public remote no
   longer serves the leaked address.
6. Consumers should re-clone or hard-reset to the scrubbed history.

## Follow-ups (outstanding)

| ID | Action | Owner |
|----|--------|-------|
| F1 | Run `python3 scripts/secrets_scan.py` on every tag | Release engineer |
| F2 | ~~Rewrite git history~~ **Done** (`git-filter-repo`); notify forks to re-clone | Maintainer |
| F3 | Confirm production & UAT Lovelace/raw configs have no private IPs after deploy | Operator |
| F4 | Wire secrets scan into CI when CI is added | Engineering |
| F5 | Security + architecture acknowledgment on next release checklist | Process |

## Process change

Security review is now **blocking** for initial feature ship and **each**
version tag. See `docs/SECURITY_REVIEW.md`.

## Role acknowledgments

- **Maintainer:** owns verification that tip is clean and CoE is accurate.
- **Security reviewer:** validates scan coverage and history-rewrite completion.
- **Architecture reviewer:** confirms the gate is adequate for continued HACS
  distribution.

## Sign-off

| Role | Date | Result |
|------|------|--------|
| Maintainer | 2026-08-22 | Tip scrubbed; history rewritten; scan OK |
| Security reviewer | | |
| Architecture reviewer | | |
