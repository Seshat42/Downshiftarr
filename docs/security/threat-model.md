# Downshiftarr Threat Model

Last reviewed: 2026-05-28

References checked for this baseline:

- Plex Support: Finding an authentication token / X-Plex-Token
- Plex API documentation: `X-Plex-Token` header authorization on Plex APIs
- Tautulli custom script documentation: injected `PLEX_URL`, `PLEX_TOKEN`, `PLEX_USER_TOKEN`, `TAUTULLI_URL`, and `TAUTULLI_APIKEY`
- Tautulli API reference: `api/v2` requests authenticated with `apikey`
- Plex Support: transcoder settings and transcoding behavior

## Scope

Downshiftarr is a Tautulli-triggered Plex enforcement script. Its security boundary includes:

- `Downshiftarr.py`, which reads Plex/Tautulli tokens, inspects active Plex sessions, selects fallback media, sends client-control commands, and terminates sessions when policy requires it.
- `Downshiftarr.env`, deployment environment variables, and Tautulli-injected script environment.
- The optional `Plex Transcoder` shim, which can run in the Plex transcoder execution path.
- Logs written to `LOG_FILE`, stderr captured by Tautulli, and optional Tautulli notification history.
- CI/test/scan artifacts used to prove policy and secret-handling behavior.

## Assets

- Plex admin token: `PLEX_TOKEN`.
- Plex user token: `PLEX_USER_TOKEN`.
- Tautulli API key: `TAUTULLI_APIKEY`.
- Plex session identifiers: `session_id`, `session_key`, machine/client identifiers, user names, rating keys, player names, addresses, and ports.
- Media metadata: selected media height, dynamic range, media ids, file names, version lists, and fallback choices.
- Enforcement authority: client remote-control commands and session termination through Tautulli or Plex.
- Plex transcoder execution path when the shim is installed.

## Trust Boundaries

- Tautulli event payloads are trigger data only. They can be stale, incomplete, or shaped by notification configuration.
- Plex session metadata is the source of truth once a session is matched.
- Local env files and process environment are trusted only if filesystem permissions and service/container boundaries are correct.
- Plex/Tautulli HTTP APIs are trusted only over the configured local or private network path. Do not expose unauthenticated or token-bearing endpoints publicly.
- The `Plex Transcoder` shim is a high-privilege local integration point because Plex invokes it while handling playback.
- The Loki test rig is a separate local-only trust boundary. Real integration tests must prove the loopback Plex identity before any mutation and must never target Bragi, TooB, relay, or external Plex URLs.

## Primary Threats

### Token Leakage

Plex and Tautulli tokens grant operational authority over the media server and monitoring plane. They must not be committed, printed, copied into screenshots, or stored in world-readable files.

Consolidation status: PR #10 / branch `fix-plex-token-exposure-14819038041623419576` was incorporated into the single-main merge. Direct Plex termination and the optional shim now send Plex tokens through `X-Plex-Token` headers instead of URL query parameters.

Tautulli API calls still use Tautulli's documented `apikey` query parameter. Treat that as an upstream API constraint and compensate with local/private network exposure, TLS when crossing hosts, strict log redaction, and key rotation after suspected exposure.

### Privileged Transcoder Shim

The optional `Plex Transcoder` shim is riskier than the Tautulli script because it sits in Plex's transcoder execution path and delegates to the real transcoder binary.

Risks:

- A bug can break playback globally.
- Compromise of the shim or its config can affect every transcode.
- Regressions that put Plex tokens back into query strings can leak `PLEX_TOKEN` through request logs, reverse proxies, browser/history-style diagnostics, crash dumps, and copied URLs.
- Logging media paths, basenames, or API errors may expose library structure.

Minimum controls:

- Install only from a reviewed commit.
- Keep the real transcoder path explicit and immutable.
- Restrict write access to the shim, env/config, and log file.
- Prefer a dedicated local-only Plex token if a shim token is unavoidable.
- Keep a fast rollback path to the original Plex Transcoder binary.

### Fail-Closed Behavior Limits

Downshiftarr is intended to fail closed by default for protected transcodes, but fail-closed is best effort, not a hard security boundary.

Limits:

- If Plex cannot be reached, the script may lack a Plex handle for Plex-side termination.
- If Tautulli cannot be reached or lacks a matching session key, Tautulli termination can fail.
- If client discovery or remote control fails, only termination remains.
- If a notification trigger fires before Plex has registered the session, matching depends on retries and identifiers.
- Per-failure `KILL_ON_*` toggles can intentionally weaken fail-closed behavior.
- Network, relay, NAT, token scope, Plex/Tautulli version changes, or API failures can prevent enforcement.

Security posture: fail closed reduces accidental policy bypass, but deployment must still monitor failures and alert on repeated "unable to terminate" outcomes.

### Log Exposure

Logs may contain usernames, rating keys, session ids/keys, machine ids, media metadata, player details, file basenames, and exception text. They must never contain `PLEX_TOKEN`, `PLEX_USER_TOKEN`, or `TAUTULLI_APIKEY`.

Controls:

- Redact known secret names and token-looking values before logging.
- Keep debug logging off in routine production use.
- Ensure `LOG_FILE` is not world-readable and has bounded retention.
- Treat Tautulli notification history as a log sink with the same sensitivity as local logs.
- Add regression tests that fail when log output includes known secret values.

## Abuse Cases

- An attacker with read access to `Downshiftarr.env` controls Plex sessions or terminates users' streams.
- A regression or downstream deployment wrapper sends a Plex token in a query string and a reverse proxy or debug log captures it.
- A malicious local user modifies `Plex Transcoder` and gains execution in the Plex playback path.
- A noisy debug run leaks session identifiers or media paths to shared logs.
- A permissive `KILL_ON_*` configuration silently turns protected-transcode enforcement into observe-only behavior.
- A CI workflow uploads raw scan artifacts containing env files or logs with secrets.
- A developer accidentally points destructive tests at a production or external Plex server. The Loki guard rejects non-loopback URLs and unexpected machine identifiers to fail closed before library refresh or session enforcement.

## Next Security Priorities

1. Add a central redaction helper and route every log/notification message through it.
2. Add tests with sentinel secrets proving no token reaches logs, stderr, Tautulli notification payloads, or exception output.
3. Document and test secure file permissions for `Downshiftarr.env`, log files, and the optional shim.
4. Add CI secret scanning and artifact hygiene checks.
5. Add operational alerts for repeated fail-closed termination failures.
6. Decide whether the `Plex Transcoder` shim remains supported; if yes, give it a separate hardening guide and rollback checklist.
