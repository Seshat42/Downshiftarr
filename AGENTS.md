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
- For docs-only lanes, verify at minimum that only intended documentation files changed, plus any relevant repository state checks.

## Test Rig Rules

- Keep fast unit and simulated tests WSL-first and deterministic.
- Treat generated media under `artifacts/plex-test-media/` as disposable local output; never commit generated videos, manifests from private runs, screenshots, logs, or tokens.
- Real Plex integration tests may target only the local Windows Plex server named Loki through the guarded loopback runner.
- Do not point real-server tests at Bragi, TooB, remote Plex hosts, relay URLs, or any non-loopback Plex URL.
- Destructive Loki tests require explicit local opt-in through `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1`.
