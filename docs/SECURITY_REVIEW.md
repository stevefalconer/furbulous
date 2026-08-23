# Security review gate (initial + every deployment)

This checklist is mandatory **before the first public/HACS release of a change
set** and **again before every tagged deployment** (`vX.Y.Z`). It supplements
the ordinary code review.

## Reviewers

| Role | Responsibility |
|------|----------------|
| **Maintainer** | Owns the Correction of Errors (CoE) write-up; verifies functional and security findings are addressed or explicitly waived. |
| **Security reviewer** | Secrets/PII scan, threat model deltas, dependency and auth-path review. Blocks release on unresolved **High** findings. |
| **Architecture reviewer** | Sign-off that process was followed and residual risk is acceptable for release. |

Reviews are recorded under `docs/reviews/` (CoE + review summary). Do not paste
secrets into those files.

## Hard rules (blockers)

1. **No LAN/WAN IPs, hostnames of private HA instances, emails, passwords,
   tokens, or Bearer headers** in tracked source, docs, dashboards, tests
   fixtures meant for git, or example YAML. Use placeholders
   (`<HA_HOST>`, `<redacted-email>`, `notify.mobile_app_YOUR_PHONE`).
2. **No credentials in commit messages or tags.**
3. **Diagnostics and logs** must keep redacting `password`, tokens, and auth
   headers (see `custom_components/furbulous/diagnostics.py`).
4. **Test passwords** may only be fake values in unit tests (`"secret"`,
   `"wrong"`) — never production or UAT credentials.

## Initial review (new major surface or first ship of a feature)

- [ ] Threat model: what new data leaves the LAN? (cloud API, notifications)
- [ ] Auth path: login, token storage, reauth — no secret logging
- [ ] Entity / dashboard examples: no site-specific IPs or account names
- [ ] Automations examples: no real `notify.mobile_app_*` device names that
      identify a household
- [ ] Run secrets scan: `python3 scripts/secrets_scan.py`
- [ ] Formal code review completed; bugs closed or waived
- [ ] Security reviewer sign-off
- [ ] Architecture reviewer sign-off

## Each deployment (every version tag / HACS publish)

- [ ] Diff since last tag reviewed for secrets (scan + human pass on docs)
- [ ] Changelog has **no** private hostnames/IPs/emails
- [ ] Production/UAT configs updated from scrubbed examples (not the reverse)
- [ ] After deploy: confirm live Lovelace/automations do not embed private IPs
- [ ] If a prior release leaked secrets in git history: tip is clean **and**
      CoE documents whether history rewrite is required
- [ ] Tag only after Security reviewer + Maintainer approve

## Secrets scan

```bash
python3 scripts/secrets_scan.py
```

Exit code non-zero blocks merge/tag.

## Correction of Errors (CoE)

When a leak or security defect ships:

1. Remove/fix tip of tree immediately and deploy the corrected artifact.
2. File `docs/reviews/COE-YYYY-MM-DD-<slug>.md` with root cause, blast radius,
   fix, and follow-ups.
3. Maintainer + Security reviewer + Architecture reviewer acknowledge.
4. Do **not** put the secret values again into the CoE — describe class only
   (e.g. “private LAN IPv4 in dashboard comment”).
