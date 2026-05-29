# Downshiftarr Agent Operating Rules

## Scope

These instructions apply to the entire `C:\Users\D3\Documents\Downshiftarr` workspace, also available in WSL at `/mnt/c/Users/D3/Documents/Downshiftarr`.

## Operating Mode

- Work WSL-first for development, testing, and repository operations when practical.
- You can use root in WSL when it is genuinely needed.
- Always reference the latest documentation for tools, frameworks, libraries, APIs, and platform behavior before making decisions that may depend on current behavior.
- Ask the user for clarification when requirements, ownership, risk, or expected behavior are uncertain.
- Act as the senior principal developer: coordinate the overall direction, assign independent work to subagents where available, and keep the big picture coherent.
- Use multiple continuous subagents for parallel lanes whenever the task can be split safely. When a subagent finishes, assign another useful task instead of leaving capacity idle.
- Treat the user as the human operator who can perform real-world or external tasks that agents cannot complete directly.

## Repository Safety

- You are not alone in this codebase. Expect other agents or the user to have concurrent edits.
- Do not revert, overwrite, or normalize edits you did not make unless the user explicitly asks.
- Before editing, inspect current file state and `git status` so ownership is clear.
- Do not merge, delete, or rewrite branches unless the user explicitly authorizes the phase. The 2026-05-28 single-main consolidation was explicitly authorized; keep future branch work deliberate and recorded.
- Keep branch-collision risks visible in `POSTERITY.md`, including active branches, uncommitted files, and any discovered conflicts.
- GitHub is approved only as remote Git storage. Do not add workflows, hosted checks, hosted releases, issues, projects, wiki, discussions, or pull-request workflow dependence.
- Do not add GitHub-hosted Plex, Tautulli, Loki, browser, or local test secrets.
- Local verification remains authoritative for local runtime proof. Use `scripts/testing/verify_local.py` and the documented WSL gates before pushing to `origin`.

## Implementation Standards

- Implement rigorous testing for all code changes. Tests should cover normal behavior, edge cases, and regressions relevant to the change.
- Keep code optimized, elegant, and maintainable. Prefer clear design and repo-consistent abstractions, even when that requires a larger rewrite.
- Follow existing project style and architecture unless there is a documented reason to change it.
- Avoid speculative refactors outside the requested scope.
- Verify changes against the real project runtime or the closest available local proof path.

## Documentation And Memory

- Ensure documentation exists and stays updated with behavior, setup, verification, and operational decisions.
- Always reference `POSTERITY.md` before meaningful work and update it with durable context after meaningful work.
- Maintain current and past knowledge compacted inside `POSTERITY.md`.
- Capture question-and-answer moments in `POSTERITY.md`, including the date, context, the exact decision or answer, and any follow-up expectations.
- Keep `AGENTS.md` updated when operating rules change.

## Verification Expectations

- Record verification commands and results in the final response for each task.
- If verification cannot be run, state why and record the remaining risk.
- The official all-up gate is `python scripts/testing/verify_local.py` from the repository root.
- The legacy `--ci` flag is a local extra-hygiene alias only. It is not a hosted check and is not an acceptance authority.
- Manual hardening campaigns are not part of the default local gate. Use `python scripts/testing/verify_hardening_setup.py` to verify setup only, and use `docs/testing/hardening-initial-runs.md` for the intentionally manual fuzz/property/monkey/chaos/mutation/boundary run list.
- For docs-only lanes, verify at minimum that only intended documentation files changed, plus any relevant repository state checks.

## Test Rig Rules

- Keep fast unit and simulated tests WSL-first and deterministic.
- Treat generated media under `artifacts/plex-test-media/` as disposable local output; never commit generated videos, manifests from private runs, screenshots, logs, or tokens.
- Real Plex integration tests may target only the local Windows Plex server named Loki through the guarded loopback runner.
- Do not point real-server tests at Bragi, TooB, remote Plex hosts, relay URLs, or any non-loopback Plex URL.
- The local Tautulli sidecar must be isolated to `downshiftarr-tautulli`, Downshiftarr labels, loopback ports, and ignored `artifacts/local-tautulli/` config.
- Never stop, remove, reconfigure, or rely on containers, ports, libraries, or installs owned by other projects.
- Destructive Loki tests require explicit local opt-in through `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1`.
- Hardening runners for native fuzz, monkey, chaos, and mutation require `DOWNSHIFTARR_HARDENING_MANUAL=1` plus an explicit `--run` flag. These runners must default to list or dry-run behavior, use fakes/synthetic inputs unless a future plan explicitly says otherwise, redact known secret env values, and keep corpora/crashes/reports under ignored hardening artifact paths.
- Default transcode behavior must preserve Plex UX while reducing server load: protected 4K/HDR/DV sources downshift to the best compliant version, and continued video transcodes should waterfall through lower available versions down to `WATERFALL_MIN_HEIGHT` (360p by default) without terminating the lowest-version session merely because no lower fallback remains.
- Downshiftarr may downshift only across Plex Versions for the same release. Do not cross Plex Editions such as theatrical, director's cut, 3D, or special-edition releases; edition metadata or `{edition-...}` naming mismatches must pass through instead of swapping.
- The Plex Transcoder shim should prefer a fresh precomputed version index when available, then fall back to bounded Plex search/section scans when `ALLOW_LIVE_LOOKUP_ON_INDEX_MISS=1`, so first-segment decisions stay fast while still preferring a proven lower Plex Version.
- The Plex Transcoder shim has a 100 ms default decision budget. Cap Plex API timeouts to the remaining budget and pass through rather than making Plex clients wait when confidence or timing fails, including when strict unsure-kill policy would otherwise apply.
- Broad evaluation should use shadow mode plus sanitized aggregate telemetry first. Telemetry may contain outcome counters, client-family buckets, version-index status, latency percentiles, no-fallback diagnostics, and adaptive-rule confidence only; never store raw usernames, tokens, IPs, rating keys, session ids, machine identifiers, or watch timelines.
- Adaptive fallback learning is client-family only and conservative. Promotion is allowed only from sanitized aggregate outcomes after at least 30 observations, at least 95% success, no recent playback/downshift failures, no edition/version ambiguity, and p95 decision latency below 75 ms; deterministic rules remain the fallback when confidence is low.
- Local client coverage uses a tiered lab: official Android SDK/Emulator AVDs where feasible, synthetic fixtures for every modeled Plex family, and documented physical-device follow-up for Apple simulators, Roku, consoles, and retail smart-TV quirks that cannot be proven on this Windows/WSL host.
