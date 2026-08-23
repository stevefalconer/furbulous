# Security and deployment review — 2026-08-22

Joint review of the private-IP documentation leak remediation, pause-hub
correctness, and release gates. Roles only (no named individuals).

| Role | Focus |
|------|--------|
| Maintainer | Correctness of tip, CoE accuracy, implement fixes |
| Security reviewer | Secrets exposure, auth/diagnostics, scan coverage |
| Architecture reviewer | Silent failure modes, process that actually runs |

## Disposition

**Approve with changes** — tip is scrubbed and history rewritten; remaining
items below should land before or with the next tag.

## Agreed findings

### 1. Private host in example docs (resolved)

- **Severity:** medium (resolved at tip + history)
- **Evidence:** former `docs/dashboards/furbulous.yaml` header
- **Fix done:** placeholders only; `git-filter-repo`; force-push; local backup
  branch deleted; `scripts/secrets_scan.py` + `docs/SECURITY_REVIEW.md`
- **Status:** closed

### 2. Secrets scan not enforced in CI (open → fixing)

- **Severity:** medium
- **Location:** missing workflow prior to this review
- **Remediation:** add `.github/workflows/secrets-scan.yml` running
  `python3 scripts/secrets_scan.py` on push/PR
- **Status:** implementing

### 3. Hub device prune deleted pause controls (resolved in 1.3.19)

- **Severity:** high (functional / availability)
- **Location:** `custom_components/furbulous/coordinator.py`
  `_async_prune_stale_devices`
- **Fix done:** skip identifiers starting with `hub_`; unit test
  `test_prune_keeps_hub_device`
- **Status:** closed (ensure HACS installs ≥1.3.19)

### 4. CoE must never re-embed secret values (resolved)

- **Severity:** low
- **Remediation:** class-only wording; scanner treats review docs specially
  but still bans private IPv4 literals
- **Status:** closed

### 5. Operator confirm live HA configs (outstanding)

- **Severity:** low
- **Action:** after deploy, confirm Lovelace/automations contain no private
  IPs (F3 on CoE)
- **Status:** open — operator

## Positive observations

- Diagnostics use `async_redact_data` for password/token fields.
- README already warns never to post passwords/tokens.
- Dashboard and notifications are separated; examples use placeholders for
  Companion notify services.

## Checklist before next tag

- [x] `python3 scripts/secrets_scan.py` exits 0
- [x] No private IPv4 in `git rev-list --all` content
- [ ] CI secrets-scan workflow on `main`
- [ ] Production/UAT Lovelace checked for private hosts
- [ ] Security reviewer + Architecture reviewer sign CoE table

## Sign-off

| Role | Result |
|------|--------|
| Maintainer | Approve with changes (CI scan + live config check) |
| Security reviewer | |
| Architecture reviewer | |
