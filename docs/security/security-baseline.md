# Downshiftarr Security Baseline

Last reviewed: 2026-05-28

This baseline is concise by design. It defines the minimum accepted security posture for Downshiftarr changes, releases, and deployments.

## Secrets and Tokens

- Store `PLEX_TOKEN`, `PLEX_USER_TOKEN`, and `TAUTULLI_APIKEY` only in `Downshiftarr.env`, the service/container environment, or Tautulli's injected script environment.
- Never commit real tokens. Example values must be obvious placeholders.
- Protect `Downshiftarr.env` with owner-only permissions, for example `chmod 600 /opt/tautulli/scripts/Downshiftarr.env`.
- Rotate Plex and Tautulli credentials after any suspected log, artifact, screenshot, repo, shell history, or proxy exposure.
- Prefer local/private network access to Plex and Tautulli. Use TLS if traffic crosses hosts or untrusted networks.

## Token Transport

- Preferred Plex API transport: send `X-Plex-Token` in the HTTP header.
- Known risk: main still has a direct Plex termination fallback that sends `X-Plex-Token` as a query parameter. The optional `Plex Transcoder` shim also has token-in-query behavior. PR #10 / `fix-plex-token-exposure-14819038041623419576` addresses these by moving Plex token use to headers.
- Tautulli `api/v2` uses `apikey` as documented by upstream. Keep Tautulli private, avoid proxy logging of query strings, and redact API keys from all artifacts.

## Plex Transcoder Shim

The optional `Plex Transcoder` shim is not a low-risk helper. It runs in Plex's playback/transcode path and should be treated as privileged operational code.

Baseline controls:

- Install only when explicitly needed.
- Review every shim change before deployment.
- Preserve the original Plex Transcoder binary and keep rollback instructions available.
- Restrict write permissions on the shim, its config/env, and its logs.
- Use header-based Plex token transport before production use.
- Keep shim logs minimal and free of tokens, full paths where possible, and raw API payloads.

## Fail-Closed Configuration

Default production posture:

- `KILL_ON_PLEX_CONNECT_FAIL=1`
- `KILL_ON_SESSION_NOT_FOUND=1`
- `KILL_ON_CLIENT_NOT_FOUND=1`
- `KILL_ON_NO_FALLBACK_MEDIA=1`
- `KILL_ON_SWITCH_FAIL=1`
- `KILL_ON_UNEXPECTED_ERROR=1`

Any deployment that disables a `KILL_ON_*` toggle must document the reason, expected duration, owner, and compensating monitoring. Fail-closed is best effort: it depends on Plex/Tautulli reachability, session matching, token validity, and available termination paths.

## Logs and Redaction

- Production default should be `LOG_LEVEL=INFO`; use `DEBUG` only during short investigations.
- Logs may include usernames, session identifiers, rating keys, machine ids, player details, and media metadata. Treat them as sensitive operational data.
- Logs must not include `PLEX_TOKEN`, `PLEX_USER_TOKEN`, `TAUTULLI_APIKEY`, or token-looking values.
- Redaction must cover local rotating logs, stderr captured by Tautulli, optional Tautulli notification entries, exception strings, and CI artifacts.
- Keep bounded retention through `LOG_MAX_BYTES` and `LOG_BACKUP_COUNT`.

## CI Gates

Required gates for security-sensitive changes:

- Unit tests: `python -m pytest` when pytest is available; otherwise `python -m unittest discover`.
- Ruff lint and format checks through the repo `pyproject.toml`.
- Dependency audit through `pip-audit`.
- Bandit over `Downshiftarr.py` and `Plex Transcoder` with `docs/security/bandit-baseline.json` as the committed
  bootstrap baseline. New findings above that baseline must be fixed or deliberately re-baselined with review notes.
- Secret scan over tracked source and docs.
- Static check that real tokens are not present in committed files.
- Regression tests for token redaction in logging and notification paths.
- A targeted check that Plex direct API fallbacks do not send `X-Plex-Token` in query parameters once PR #10 is merged.
- Artifact review proving scan outputs do not include raw env files, full secrets, or unrestricted logs.

## Scan Artifact Layout

Use this local layout for repeatable security evidence:

```text
artifacts/security/<YYYYMMDD-HHMMSS>/
  manifest.txt
  git-status.txt
  unit-tests.txt
  secret-scan.txt
  static-token-transport.txt
  log-redaction-tests.txt
  artifact-hygiene.txt
```

Artifact rules:

- Store command, timestamp, repo commit, and pass/fail status in `manifest.txt`.
- Never copy `Downshiftarr.env` into artifacts.
- Redact secrets before saving command output.
- Keep artifacts local unless reviewed for disclosure.

## Release Checklist

- Security docs reflect current behavior and open risks.
- PR #10 token-in-header behavior is merged or the release notes explicitly call out token-in-query risk.
- All `KILL_ON_*` defaults remain fail-closed unless a documented exception exists.
- Logs have redaction coverage and bounded retention.
- CI gates pass and artifacts follow the layout above.
- Optional `Plex Transcoder` shim deployment is separately approved and rollback-tested.

## Next Priorities

1. Land the PR #10 token transport fix.
2. Centralize log redaction and test it with sentinel secrets.
3. Add CI secret scanning and token-transport checks.
4. Harden or retire the optional transcoder shim.
5. Add production runbook entries for token rotation, failed termination alerts, and secure artifact handling.
