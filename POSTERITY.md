# Downshiftarr Posterity

This file preserves durable project context, decisions, Q&A, and verification expectations for future agents working in
`C:\Users\D3\Documents\Downshiftarr` and `/mnt/c/Users/D3/Documents/Downshiftarr`.

## 2026-05-28

### Current Context

- Workspace: `C:\Users\D3\Documents\Downshiftarr`.
- WSL path: `/mnt/c/Users/D3/Documents/Downshiftarr`.
- Authoritative branch: `main`.
- Remote storage: GitHub may be used only as the `origin` Git remote for fetch and push storage.
- Remote-hosted automation on the storage host was disabled on 2026-05-28; local verification remains authoritative.
- The workspace is shared with other agents or user edits; never revert others' work.
- Always inspect `git status --short --branch` before editing.

### Operating Decisions

- Work WSL-first for development, tests, lint, and security checks.
- Use local verification only; do not depend on any remote platform feature beyond plain Git fetch and push.
- Official all-up verification command: `python scripts/testing/verify_local.py`.
- Keep `AGENTS.md`, docs, and this file current when operating rules or durable decisions change.
- Ask for clarification when requirements, ownership, risk, or expected behavior are uncertain.
- Use subagents for independent lanes when available and useful.

### Bootstrap And Consolidation Summary

- Bootstrap converted the local skeleton into the project checkout, fetched branch history, and stopped before consolidation.
- A Windows case-insensitive filename collision between root test files was resolved by moving coverage into unique lowercase files under `tests/`.
- The user later authorized single-main consolidation.
- Former development, security, cleanup, and test branch content was folded into `main`.
- Non-main local and remote refs were removed after ancestry or supersession verification; tags were preserved.
- Current branch policy remains single-main unless the user explicitly opens a temporary local work lane.

### Security And Shim Summary

- `Downshiftarr.py` and the optional `Plex Transcoder` shim send Plex tokens through `X-Plex-Token` headers, not URL query parameters.
- The optional shim remains privileged because it runs in the Plex transcode path.
- Real tokens belong only in ignored local env files or deployment environment variables.
- Logs, screenshots, scan output, generated media manifests, and proof artifacts must not contain secrets.

### Robust Test Environment

- The repository has a layered local test rig: fast unit tests, deterministic simulated Plex/Tautulli/client tests, generated-media tests, and opt-in Loki Plex integration.
- Loki is the local Windows Plex server for real integration proof only.
- WSL remains the primary deterministic verification shell.
- Windows PowerShell is the runner for real Loki checks because Windows can reach `http://127.0.0.1:32400` and WSL currently cannot.
- Observed Loki identity on 2026-05-28: Plex Media Server `1.43.2.10687-563d026ea`, machineIdentifier `165cc0187d76937eb104da8d46437bf5443ec503`.
- Real-server tests must not target Bragi, TooB, relay URLs, hosted Plex, external Plex, or any non-loopback server.
- Generated test media belongs under ignored `artifacts/plex-test-media/`.
- Local test secrets belong only in ignored `Downshiftarr.test.env`.
- The local Tautulli sidecar is isolated to `downshiftarr-tautulli`, loopback port `18181` or first free `18182-18190`, and ignored `artifacts/local-tautulli/`.
- User clarified that no existing installations or other projects may be impacted by this test rig.
- User approved destructive actions on Loki as a local test server, limited to Downshiftarr generated media, test sessions, and dedicated test library assets.
- On 2026-05-28 the sidecar API reported `status=success`, `server_status.connected=true`, and `get_activity` returned an empty successful activity payload.
- Browser smoke reached the Tautulli sidecar via `http://host.docker.internal:18181` and saw `Tautulli - Home | Loki`; it also reached Loki's `/identity` endpoint through `host.docker.internal` without placing a Plex token in the URL.
- Chrome local smoke reached `http://127.0.0.1:18181` and saw `Tautulli - Home | Loki`; Chrome blocked direct Plex `/identity` navigation with `ERR_BLOCKED_BY_CLIENT`, so authenticated Plex Web playback proof remains a follow-up.

### Q&A And User Instructions

- Q: How should uncertainty be handled?
- A: Ask the user for clarification, and preserve the question, answer, and context in this file.

- Q: How should verification be handled?
- A: Run rigorous local verification appropriate to the change, then record commands and outcomes in the final response.

- Q: Which real Plex server may be mutated for test proof?
- A: Only Loki, the local Windows Plex server, after `scripts/testing/loki_guard.py` verifies loopback URL plus expected Plex machine identity.

- Q: Can destructive tests refresh a real Plex library or terminate sessions?
- A: Yes, but only for the dedicated Loki generated-media test lane after `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1` is set in ignored local config.

- Q: Should remote automation or remote code scanning run for this repo?
- A: No. The user explicitly decided GitHub is remote repository storage only. Verification is local.

- Q: How are smart TV and other client behaviors covered without every device present?
- A: The simulated harness models Plex Web, Roku, Apple TV, Android TV/Fire TV, Chromecast, Samsung Tizen, LG webOS, consoles, mobile, Plex HTPC, relay, and unknown clients. Real devices can be added as follow-up proof, but deterministic simulated coverage comes first.

- Q: May the local Tautulli test setup use existing installs or other project containers?
- A: No. The Tautulli sidecar must use Downshiftarr-only Docker names, labels, loopback ports, ignored config, and label-guarded cleanup.
