# Downshiftarr Posterity

This file preserves durable project context, decisions, Q&A, and verification expectations for future agents working in
`C:\Users\D3\Documents\Downshiftarr` and `/mnt/c/Users/D3/Documents/Downshiftarr`.

## 2026-05-28

### Current Context

- Workspace: `C:\Users\D3\Documents\Downshiftarr`.
- WSL path: `/mnt/c/Users/D3/Documents/Downshiftarr`.
- Authoritative branch: `main`.
- GitHub may be used only as remote Git storage for `origin/main`.
- Prior remote-hosted automation and release decisions were superseded on 2026-05-28 by the Bragi/Downshiftarr integration decision: no hosted workflows, no hosted releases, no pull-request workflow dependence, and local/live verification is authoritative.
- Previous repository setting observations about hosted automation are historical only and no longer describe the accepted operating model.
- The workspace is shared with other agents or user edits; never revert others' work.
- Always inspect `git status --short --branch` before editing.

### Operating Decisions

- Work WSL-first for development, tests, lint, and security checks.
- Do not add remote hosted automation, hosted checks, hosted release jobs, or pull-request workflow dependence without a new user decision.
- Official all-up local verification command: `python scripts/testing/verify_local.py`.
- Official local extra-hygiene command: `python scripts/testing/verify_local.py --ci`.
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
- Git remote storage must not receive Plex, Tautulli, Loki, browser, or local test secrets.

### Robust Test Environment

- The repository has a layered local test rig: fast unit tests, deterministic simulated Plex/Tautulli/client tests, generated-media tests, and opt-in Loki Plex integration.
- Hardening setup now includes manual-only fuzz, property-based, monkey, chaos, mutation, and boundary value lanes. Setup verification is separate from campaign execution.
- Official hardening setup command: `python scripts/testing/verify_hardening_setup.py`.
- Durable hardening run checklist: `docs/testing/hardening-initial-runs.md`.
- Native Atheris fuzzing uses the WSL Python 3.11 lane managed by `uv`; normal project gates continue to use Python 3.12.
- User approved installation of required development tools. On 2026-05-28, WSL build tooling was installed with root for clang, LLVM, build-essential, and pkg-config; Ubuntu did not publish `python3.11` apt packages in this environment, so `uv python install 3.11` was used.
- Hardening campaigns are not run automatically by `scripts/testing/verify_local.py`; the default non-destructive pytest lane excludes `property`, `fuzz`, `native_fuzz`, `monkey`, `chaos`, `mutation`, and `boundary`.
- Native fuzz, monkey, chaos, and mutation runners require `DOWNSHIFTARR_HARDENING_MANUAL=1` plus `--run`; list and dry-run modes are the setup-safe default.
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
- A: Superseded on 2026-05-28. No; GitHub is remote Git storage only. Real local-service proof remains local.

- Q: How often should GitHub releases be created?
- A: Superseded on 2026-05-28. Do not create automated hosted releases in this pass; old tags are preserved but not an acceptance path.

- Q: May hosted automation receive real local integration credentials?
- A: No. Plex, Tautulli, Loki, browser, Docker sidecar, and local test secrets stay out of Git remote storage and any future hosted automation.

- Q: How are smart TV and other client behaviors covered without every device present?
- A: The simulated harness models Plex Web, Roku, Apple TV, Android TV/Fire TV, Chromecast, Samsung Tizen, LG webOS, consoles, mobile, Plex HTPC, relay, and unknown clients. Real devices can be added as follow-up proof, but deterministic simulated coverage comes first.

- Q: May the local Tautulli test setup use existing installs or other project containers?
- A: No. The Tautulli sidecar must use Downshiftarr-only Docker names, labels, loopback ports, ignored config, and label-guarded cleanup.

- Q: Should the fuzz/property/monkey/chaos/mutation/boundary hardening setup run the initial campaigns now?
- A: No. This phase is setup only. It must create the environment, scripts, tests, and durable checklist, then leave the first real campaign runs as manual follow-up commands.

- Q: Which native fuzzing engine is required?
- A: Atheris is required for the native fuzz lane, isolated to WSL Python 3.11 through `uv`.

- Q: Which mutation runner is the default?
- A: `mutmut` is the default mutation-testing runner.

- Q: May development tools be installed for this setup?
- A: Yes. The user approved installing any needed development tools.

- Q: Should Downshiftarr stop after a single 4K/HDR downshift?
- A: No. On 2026-05-28 the user required automatic waterfall behavior: if a client continues video-transcoding after the first downshift, Downshiftarr should keep stepping through lower available versions down to the lowest configured target, 360p by default. The lowest-version case should preserve Plex UX and pass through rather than terminate solely because no lower version exists.

### 2026-05-28 Waterfall Hardening

- Added default-enabled `AUTO_WATERFALL_ON_CONTINUED_TRANSCODE=1` and `WATERFALL_MIN_HEIGHT=360` to the Tautulli script and Plex Transcoder shim paths.
- Expanded fallback preferences to `1080,720,576,480,360` so both controller paths can continue 1080 -> 720 -> 480 -> 360 when a client still transcodes.
- Added regression tests proving continued-transcode waterfall selection, shim-level waterfall interception, 360p inclusion, and lowest-version pass-through without termination.
- Built local-only real-media canary ladders under the Hardening repo's ignored `.sample-media/downshiftarr-waterfall/` path from the operator-provided Deli Boys and WALL-E samples: protected HDR sources plus SDR 1080/720/480/360 versions with varied audio layouts. These files must never be committed or uploaded to GitHub.
- Verification passed: `scripts/testing/verify_local.py`, `scripts/testing/verify_local.py --hardening-setup`, boundary/property/fuzz pytest lanes, monkey fallback/client-event campaigns, chaos fake-service/client-control/malformed-metadata campaigns, and bounded Atheris parser/shim native fuzz runs.

### 2026-05-28 Bragi Plex Shim Runtime Correction

- Bragi live canary testing showed the Plex service could execute the shim file but AppArmor denied the shebang-resolved Python interpreter path, producing `/usr/bin/env: 'python3': Permission denied` during real Plex-spawned transcodes.
- The Linux `Plex Transcoder` shim now uses an absolute `/usr/bin/python3` shebang, with a regression test and README note, so confined Plex deployments can allow the exact interpreter path instead of relying on `PATH` resolution through `/usr/bin/env`.
