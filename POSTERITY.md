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

### 2026-05-28 Bragi Plex Shim Token File Correction

- Bragi live HLS canary testing showed that Plex-spawned transcodes do not reliably provide `X_PLEX_TOKEN` to the shim. Without a token, the shim could execute but could not perform the local Plex metadata lookup needed to swap to a lower compatible version before the real transcoder started.

## 2026-05-28 Plex Versions And Speed Index Follow-Up

- Q: Should Downshiftarr waterfall across Plex Editions? A: No. The operator provided Plex's multi-version guidance and selected Versions Only. Downshiftarr must downshift only across Plex Versions for the same release; theatrical, director's cut, 3D, and special-edition surfaces are not interchangeable fallback targets.
- Implemented conservative edition guards in both `Downshiftarr.py` and the Plex Transcoder shim. They compare Plex edition fields and `{edition-...}` file-name tokens, and pass through when the current media and candidate fallback do not share the same edition key.
- Added optional shim support for `/var/lib/downshiftarr/cache/plex-version-index.json`. The shim checks that precomputed index before live Plex search/section scans so Bragi can keep first-segment decisions fast while still falling back to bounded Plex lookups when the index is absent or stale.
- Added regression coverage for edition mismatch refusal, same-edition fallback, and version-index lookup before Plex API search.
- The shim now supports `PLEX_TOKEN_FILE` in external JSON config. It reads one root-owned, regular, non-symlink token file at runtime, rejects group/other writable or other-readable files, keeps token values out of argv/process environment, and falls back to no lookup when the file is unsafe.

## 2026-05-28 Speed-First Shadow And Telemetry Follow-Up

- Q: Should the next Downshiftarr pass prioritize absolute enforcement or Plex client speed? A: Speed and UX first. Broad evaluation should run in shadow mode, and active downshift should stay targeted to proven risky protected Plex Versions.
- Added a 100 ms default decision budget to the Plex Transcoder shim. The shim now caps Plex API request timeouts to the remaining decision budget and passes through when the budget is exhausted, rather than making Plex clients wait.
- Added sanitized aggregate telemetry to both the shim and `Downshiftarr.py`: outcome counters, client-family buckets, version-index statuses, and latency summaries only. Raw usernames, tokens, IPs, rating keys, session ids, machine identifiers, and watch timelines remain out of telemetry.
- Added shadow-mode paths for both controller layers. Shadow mode records would-be downshift candidates and immediately passes through without Plex remote-control changes or input-file swaps.
- Added regression coverage for budget exhaustion before lookup, budget-capped Plex HTTP timeouts, stale/empty version-index diagnostics, sanitized telemetry, shadow-mode pass-through, and mismatched `plex.client(player_title)` identifier refusal.

## 2026-05-28 Emulator-Lab And Adaptive Learning Follow-Up

- Q: Should this pass wait for physical Pixel/iPad/Roku/TV devices? A: No. The operator selected the heaviest feasible legitimate emulator lab plus synthetic release proof for this pass; physical client proof can be appended later.
- Q: Should Downshiftarr learn automatically from Bragi outcomes? A: Yes, but only shadow-first with sanitized aggregate outcomes, confidence thresholds, and bounded churn. Deterministic rules remain authoritative until a learned fallback is promoted.
- Q: Should Plex clients ever wait for Downshiftarr? A: No. The shim keeps the 100 ms p95 budget and passes through when cache, confidence, or timing is not good enough.
- Implemented sanitized adaptive learning state in `Downshiftarr.py` for client-family/media-risk/fallback-height candidates. The state records aggregate success, continued-transcode, abandonment, and shadow counters only; it does not store usernames, tokens, IPs, rating keys, machine identifiers, session ids, or raw watch timelines.
- Improved fallback scoring in both `Downshiftarr.py` and the Plex Transcoder shim so equal-height fallback candidates prefer broadly compatible audio and subtitle tracks, reducing forced audio transcodes and subtitle burn-in risk.
- Added per-client-family p50/p95 latency telemetry and cache-oversize fail-open handling to the shim.
- Added `scripts/testing/emulator_lab.py` and tests. The ignored local lab now contains a portable Android SDK/JDK setup with AVDs for Android mobile, Android tablet, Android TV, and Google TV. Samsung Tizen and LG webOS official emulator tooling remains documented as unavailable through the current unattended Windows package path; Apple simulators require macOS/Xcode; Roku and console retail Plex behavior requires physical hardware or synthetic proof.

## 2026-05-29 Downshift-First Conservative Promotion Follow-Up

- Q: Should Downshiftarr prefer downshift over pass-through when the hot version index misses? A: Yes, but only inside the existing 100 ms shim budget and only when Plex proves a lower compatible Version of the same item/release/edition.
- Q: Should adaptive learning promote rules automatically? A: Yes, but only by sanitized client family after at least 30 observations, 95% or better success, no recent playback/downshift failures, no version/edition ambiguity, and p95 decision latency below 75 ms.
- The Plex Transcoder shim now exposes `ALLOW_LIVE_LOOKUP_ON_INDEX_MISS`, records `live_lookup_waterfall_swap` telemetry, uses bounded live Plex lookup after an index miss, skips extra metadata fetches when the version index already carries enough sibling `Media` metadata, and passes through if the decision budget expires even when strict unsure-kill is enabled.
- `Downshiftarr.py` now treats adaptive promotion as aggregate-only trust data. It rejects unknown-family promotion, records candidate latency/recent outcomes, supports sanitized adaptive outcome ingestion for Tautulli hooks, and keeps raw usernames, tokens, IPs, rating keys, machine identifiers, session ids, device ids, and timelines out of durable state.

## 2026-05-29 No-4K-Transcode Production Invariant

- Q: Is 4K content ever allowed to transcode? A: No. The operator made this a hard requirement: if Plex starts transcoding a 4K source, Downshiftarr must immediately use a fresh verified same-item/same-edition Plex Versions index to swap lower, or block the 4K transcode.
- Q: What happens when no lower version is proven? A: Block the 4K transcode. Playback continuity is handled by Bragi media-readiness policy and Plex Versions proof, not by allowing a 4K transcode to continue.
- Q: May runtime 4K decisions depend on slower live lookup? A: No. A fresh version index is mandatory for 4K decisions. Live lookup remains available only for non-4K continued-transcode diagnostics.
- Q: How should new 4K media be handled? A: Downshiftarr must not generate media. Bragi media intake must already provide at least one lower Plex Version, normally 1080p or 720p, before a protected 4K item is considered ready.
- Superseded note: an earlier 2026-05-29 planning phrase used "auto-generate lower versions"; the current locked policy replaces that with version-readiness validation only.
- The Plex Transcoder shim now defaults to `FOUR_K_TRANSCODE_ALLOWED=false` and `REQUIRE_FRESH_INDEX_FOR_4K=true`. It blocks 4K pass-through on missing/stale/future/untimestamped indexes, cache-only hits, lookup uncertainty, budget exhaustion, and shadow mode.
- `Downshiftarr.py` also enforces the invariant: relaxed no-fallback toggles and shadow mode cannot let a 4K video transcode continue.

## 2026-05-29 Device-Blind Shim Clarification

- Q: Should the Plex Transcoder shim prioritize device identification? A: No. The operator clarified that once Plex invokes the shim, the transcode itself is the important signal. Device/client-family classification must stay out of the shim hot path.
- Q: Where may client-aware behavior remain? A: Only in the Tautulli/Downshiftarr controller layer when needed to target the correct session, preserve resume/seek behavior, record sanitized aggregate outcomes, or perform asynchronous diagnostics.
- Q: What fallback order should device-blind enforcement use? A: Prefer 1080p SDR first, then waterfall to 720p, 480p, and 360p if video transcoding continues.
- Shim telemetry is now aggregate-only for outcomes, version-index status, and latency. It no longer records `client_families` or `latency_by_client_family`.

## 2026-05-30 Device-Blind >1080 Protected Source Refresh

- Q: How should cinematic 4K-ish heights be classified? A: Any actual video height above 1080 is protected; the source threshold is `PROTECTED_SOURCE_MIN_HEIGHT=1081`.
- Q: Should adaptive learning influence fallback? A: No. Adaptive learning is disabled for this pass; deterministic fixed fallback order is authoritative.
- Q: What should happen when the Plex Versions index is missing or stale? A: The shim always attempts a bounded local Plex lookup inside the same 100 ms budget. Protected `>1080` sources still block if proof or time runs out; non-protected continued waterfall paths pass through on uncertainty.
- Q: How should 1080 HDR/remux behave? A: Waterfall by default, but do not hard-block solely for missing lower fallback. A future config may hard-protect 1080 HDR/remux if explicitly reapproved.
- Bragi cache freshness target is 60 seconds. Downshiftarr continues to validate existing Plex Versions only and does not generate media files.

## 2026-05-30 Protected-Waterfall Speed Refinement

- Q: What cache and lookup semantics should the shim use? A: Fresh index/cache first, then bounded Plex lookup on miss or stale evidence. Protected sources block if proof fails; non-protected sources pass through on proof or budget uncertainty.
- Q: How should 1080 remux-like sources be identified? A: Keep 1080 remux as waterfall-by-default and use `REMUX_1080_MIN_BITRATE_KBPS=25000` as the initial configurable bitrate threshold.
- Q: Should `Downshiftarr.py` share the same policy contract as the shim? A: Yes. The Tautulli script and shim should agree on protected height, remux-like detection, fallback order, and same-item/same-edition boundaries.
- Implementation note: the shim now exposes a dedicated `protected_waterfall_decision` entrypoint, keeps generic fallback-cache use behind fresh actual-height proof, defaults `CACHE_TTL_S=60`, and treats bitrate-derived 1080 remux-like transcodes as waterfall candidates without enabling hard block by default.

## 2026-05-30 Compact Index And Config Guard Follow-Up

- Q: Should the shim add a compact Plex Versions index format? A: Yes. The operator selected compact v2 so the hot path can avoid scanning broad item-shaped records. Earlier transition compatibility is historical only; active policy rejects non-v2 indexes.
- Q: How should unsafe config ranges behave? A: Fail closed for protected playback. The shim now rejects unsafe numeric ranges at config load rather than silently accepting drift; protected decisions still use source/version proof and the non-protected path keeps the existing pass-through-on-uncertainty UX policy.
- Q: Should 1080 remux-like sources become hard-protected? A: No. The default remains waterfall-only; hard protection stays behind explicit config.
- Historical implementation note: the shim can load compact v2 indexes keyed by part path, converts them into the existing same-item/same-edition decision model, records `hit_v2` telemetry, and exposes `attempt_protected_waterfall_fast_path` before generic lookup/cache logic. Temporary v1 compatibility from this rollout is superseded; active policy treats every non-v2 index as invalid.

## 2026-05-30 Plex API Authoritative Waterfall Decision

- Q: Should the shim rely on a fresh index as the authoritative Versions source? A: No. The operator selected Plex API always. The compact v2 index is only an exact path-to-`ratingKey` locator; every waterfall swap must use `/library/metadata/{ratingKey}` as the current authoritative Plex Versions list.
- Q: Should v1 index compatibility remain? A: No. Older v1 item-shaped indexes are now rejected and must be regenerated as compact v2 locators before Bragi proof can pass.
- Implementation note: basename Plex search was removed from the swap authorization path. If the v2 locator misses, the shim may use a bounded section-location exact `Part.file` lookup to find the item, then must fetch `/library/metadata/{ratingKey}` before selecting `1080 SDR -> 720 -> 480 -> 360`.

## 2026-05-31 Authoritative Lookup Follow-Up

- Q: Should protected metadata lookup get a retry? A: Yes, one immediate retry inside the same 100 ms decision budget, then block protected playback if proof is still unavailable.
- Q: How should v1 indexes behave now? A: Delete v1 support. Any non-v2 index is invalid and may only lead to live lookup or protected blocking.
- Q: Which rating key should the Tautulli script trust? A: Prefer the matched Plex session `ratingKey`; if the Tautulli event key disagrees, log a sanitized mismatch and use the session authority.
- Implementation note: swaps now require explicit `/library/metadata/{ratingKey}` metadata; numeric `fetchItem` fallback is not allowed to authorize version selection.

## 2026-05-31 Unknown Actual-Height Fail-Closed Source Update

- Q: Can the Plex Transcoder shim pass through a streaming transcode when the source filename is neutral and neither the v2 path locator nor authoritative Plex metadata proves actual height before the decision budget expires? A: No. The shim now treats unknown actual height as fail-closed before invoking the real Plex Transcoder, records `unknown_actual_height_blocked`, and preserves normal pass-through only when metadata or an explicit resolution token proves the source is not protected.
- Implementation note: this moves the Bragi safety behavior into the Downshiftarr source repo so deployment no longer depends on an install-time source patch for `unknown_actual_height_blocks=pass`.

- 2026-06-01 local verifier hardening: The official Windows local gate now normalizes the committed Bandit baseline path separators at runtime, so Bandit still enforces the same baseline on Windows and Linux. Hardening setup now treats Atheris/native-fuzz on Windows as target-list proof instead of a false build requirement; Linux/Bragi retains the import/build check. Verified with `python scripts/testing/verify_local.py --hardening-setup`: local verification passed with 441 non-destructive tests passed, 4 Windows-only POSIX skips, simulated/media/security checks, gitleaks, Bandit normalized baseline, and hardening setup target listing.

- 2026-06-01 Plex Transcoder cache authority tightening: A full-pass sidecar audit found that the generic fallback cache could still authorize a non-protected swap after fresh actual-height proof without first fetching current Plex metadata. The shim now treats the cache only as a hint: every cache swap fetches authoritative `/library/metadata/{ratingKey}`, verifies the current and fallback files are still same-item/same-edition safe, and only then rewrites the input. Non-protected metadata uncertainty now passes through even when strict unsure-kill mode is enabled, while protected or unknown-height sources still fail closed. Added regression coverage for authoritative cache swaps, fixed `1080 -> 720 -> 576 -> 480 -> 360` waterfall ordering, and strict non-protected pass-through. Verified with targeted shim/simulated tests plus full `python scripts/testing/verify_local.py` and `python scripts/testing/verify_local.py --hardening-setup`.
