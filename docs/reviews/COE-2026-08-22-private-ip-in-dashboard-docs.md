# Correction of Errors — Private LAN IP in dashboard documentation

| Field | Value |
|-------|--------|
| **Date** | 2026-08-22 |
| **Severity** | Medium (information disclosure — private network location) |
| **Status** | Corrected at tip of `main`; **git history rewritten** with `git-filter-repo` to replace private LAN IPv4 → `<HA_HOST>` across all commits (force-push required) |
| **Principal developer / Grok reviewer** | Grok reviewer persona (process owner for this CoE) |
| **Security team** | Required sign-off on this CoE before next tag |
| **Executive architecture** | Matei Zaharia — process acknowledgment |

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
header (“THIS HOUSE (…IP…)” and a direct `http://…:8123/…` URL) instead of
using placeholders. There was no automated secrets scan in the release path.

## Blast radius

- **Public GitHub history** for several commits on `main` still contain the
  IPv4 string in `docs/dashboards/furbulous.yaml` comments.
- **HACS / clone consumers** who pulled those commits could see the address.
- **Live HA Lovelace storage** (UI dashboard) did not require that comment for
  function; risk was primarily documentation/source control.

## Immediate correction (deploy first)

1. Removed the LAN IP and direct HA URL from `docs/dashboards/furbulous.yaml`.
2. Removed loopback HA URLs from `docs/UAT_ALIGNMENT.md`.
3. Added `docs/SECURITY_REVIEW.md` (initial + every deployment gate).
4. Added `scripts/secrets_scan.py` (fails on private IPs / obvious tokens).
5. Publish corrected `main` **before** treating older tip as current deployable
   artifact. Consumers should update to the scrubbed commit / next tag.

## Follow-ups (outstanding)

| ID | Action | Owner |
|----|--------|-------|
| F1 | Run `python3 scripts/secrets_scan.py` on every tag | Release engineer |
| F2 | ~~Rewrite git history~~ **Done locally** (`git-filter-repo` replace-text). Force-push `main` + tags after Security ack; notify forks to re-clone | Security + principal developer |
| F3 | Confirm production & UAT Lovelace/raw configs have no private IPs after deploy | Operator |
| F4 | Wire secrets scan into CI when CI is added | Engineering |
| F5 | Matei Zaharia / Security acknowledgment recorded on next release checklist | Process |

## Process change

Security review is now **blocking** for initial feature ship and **each**
version tag. See `docs/SECURITY_REVIEW.md`.

## Acknowledgments

- **Principal developer (Grok reviewer persona):** owns verification that tip is
  clean and CoE is accurate.
- **Security team:** validates scan coverage and history-rewrite decision.
- **Matei Zaharia:** executive confirmation that the gate is adequate for
  continued HACS distribution.

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Principal developer (Grok reviewer) | _pending formal review run_ | 2026-08-22 | |
| Security team | _pending_ | | |
| Matei Zaharia (architecture) | _pending_ | | |
