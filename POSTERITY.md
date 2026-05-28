# Downshiftarr Posterity

This file preserves durable project context, decisions, Q&A, and verification expectations for future agents working in `C:\Users\D3\Documents\Downshiftarr` and `/mnt/c/Users/D3/Documents/Downshiftarr`.

## 2026-05-28

### Current Context

- Workspace: `C:\Users\D3\Documents\Downshiftarr`.
- WSL path: `/mnt/c/Users/D3/Documents/Downshiftarr`.
- Bootstrap objective: turn the empty local Git skeleton into a full `Seshat42/Downshiftarr` checkout, fetch every remote branch, create local tracking branches, add office docs/tooling/security baselines, and stop before branch consolidation.
- The workspace is shared with other agents or user edits; never revert others' work.
- Bootstrap rule: no branch merging, rebasing, cherry-picking, branch deletion, or branch consolidation during this phase.

### Q&A And User Instructions

- Q: What did the user ask this turn?
- A: Implement the `Downshiftarr Office Bootstrap And Branch Intake` plan.

- Q: What operating rules must be captured in `AGENTS.md`?
- A: WSL-first workflow, latest documentation, ask when unsure, senior principal developer coordinating subagents, rigorous testing, elegant and optimized code, documentation kept updated, `POSTERITY.md` maintained, Q&A captured, and no branch merging during bootstrap.

- Q: What branch workflow did the user request?
- A: Pull all branches now, then in the next phase merge into a single `main`. This docs-only lane records that instruction but does not perform branch pulls or merges.

- Q: Were branches merged in this phase?
- A: No. All remote branches were fetched and materialized as local tracking branches, but no branch histories were merged or rewritten.

- Q: What checkout issue appeared on the Windows-backed WSL path?
- A: `main` had root files named `test_Downshiftarr.py` and `test_downshiftarr.py`, which collide on the case-insensitive Windows directory. The bootstrap resolved this by moving their test coverage into unique lowercase files under `tests/`.

- Q: How should uncertainty be handled?
- A: Ask the user for clarification, and preserve the question, answer, and context in this file.

- Q: How should verification be handled?
- A: Run rigorous verification appropriate to the change. For docs-only work, verify repository status, branch state where relevant, and confirm only intended files were edited.

### Branch And Collision Notes

- Active branch after bootstrap: `main`.
- Local branches: 12. Remote tracking branches excluding `origin/HEAD`: 12.
- Tags fetched: `v0.0.2`, `v0.7.2`, `v0.7.3b`.
- `origin/HEAD` points to `origin/main`.
- `dev` remains diverged from `main` and is preserved for next-phase review.
- The root test filename collision was removed from the working tree by consolidating tests under `tests/`; do not recreate root test files that differ only by case.
- Many active feature/test branches exist and are expected to be reviewed/reconciled before the next phase merge into a single `main`.

### Verification Expectations

- Before editing: inspect `git status --short` and relevant existing docs.
- Standard bootstrap gates: `uv sync --all-groups`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pip-audit`, Bandit with the committed baseline, Gitleaks, branch-count verification, and `git diff --check`.
- Record verification commands and outcomes in the final response.
- Future code lanes must add or update tests appropriate to the changed behavior before claiming completion.

### Single-Main Consolidation

- User instruction: proceed to merge all branches into a single `main`, push to GitHub when complete, integrate and clear all pull requests, then delete every non-`main` remote branch.
- Temporary work branch: `codex/consolidate-all-branches` from local `main` at `9749e87`.
- Merge parent record:
  - `dev` via `032d710`, preserving the newer `Plex Transcoder` shim and README shim documentation.
  - PR #10 `fix-plex-token-exposure-14819038041623419576` via `adee13c`, with Plex auth moved to `X-Plex-Token` headers in both `Downshiftarr.py` and the newer shim.
  - PR #11 `fix-unused-annotations-import-14675292598164734863` via `2849525`, removing the unused future annotations import from `Downshiftarr.py`.
  - PR #9 `add-tests-media-height-4449859519764339005` via `39580ee`, ported to `tests/test_media_height.py`.
  - PR #7 `jules-8496729870724669652-24d2ecea` via `3b04a2b`, ported to `tests/test_quality_classification.py`.
  - PR #12 `jules-10351953059055018286-c854910a` via `deae9ec`, ported to `tests/test_quality_classification.py`.
  - PR #8 `jules-16002624577278156886-445e8c56` via `d2c38d8`, ported to `tests/test_helpers.py`.
  - PR #5 `testing-improvement-parse-resolution-hint-11289850538183556530` via `92e2552`, ported to `tests/test_helpers.py`; generated `__pycache__/`, `*.pyc`, and `downshiftarr.log` artifacts were dropped.
  - PR #14 `jules-311580304402418888-ae638ed7` via `fc0045a`, ported to `tests/test_helpers.py`.
- Q: Should PRs be left open if their content is included manually?
- A: No. The user asked to integrate and clear all pull requests into the single `main`; use real merge parents where practical, then close any remaining PRs only after verifying their head commits are ancestors of `origin/main`.
- Q: Should remote non-`main` branches remain after consolidation?
- A: No. The user authorized deletion of every non-`main` remote branch after the push and PR cleanup. Tags are preserved.
- Case-safety rule remains active: do not reintroduce root `test_downshiftarr.py` or `test_Downshiftarr.py`; all branch test coverage now lives under lowercase `tests/`.
- Remote cleanup outcome: `main` was pushed to GitHub at `6c70c39`; GitHub automatically marked PRs #5, #7, #8, #9, #10, #11, #12, and #14 as merged at 2026-05-28 05:37:55 UTC.
- Remote branch cleanup outcome: after ancestry verification against `origin/main`, every non-`main` remote branch was deleted. GitHub branch API returned only `main`, local remote tracking returned only `origin/HEAD -> origin/main` and `origin/main`, and the open PR list was empty.

### Robust Test Environment

- User instruction: generate a robust and in-depth testing environment for Downshiftarr using the locally installed Windows Plex server named Loki where real Plex proof is needed.
- Active implementation branch: `codex/robust-test-environment`.
- WSL remains the primary shell for development, unit tests, simulated tests, generated-media tests, lint, and security gates.
- Windows PowerShell is the intended runner for real Loki Plex integration because Windows can reach `http://127.0.0.1:32400` and WSL currently cannot.
- Loki identity observed on 2026-05-28 from Windows `/identity`: Plex Media Server `1.43.2.10687-563d026ea`, machineIdentifier `165cc0187d76937eb104da8d46437bf5443ec503`.
- Real-server tests are local-only. They must not target Bragi, TooB, relay URLs, hosted Plex, external Plex, or any non-loopback server.
- Generated test media belongs under ignored `artifacts/plex-test-media/`; do not commit videos, local manifests from private runs, screenshots, logs, or tokens.
- Local test secrets belong only in ignored `Downshiftarr.test.env`.

### Robust Test Q&A

- Q: Which real Plex server may be mutated for test proof?
- A: Only Loki, the local Windows Plex server, and only after `scripts/testing/loki_guard.py` verifies loopback URL plus expected Plex machine identity.

- Q: Can destructive tests refresh a real Plex library or terminate sessions?
- A: Yes, but only for the dedicated Loki-generated-media test lane after `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1` is set in ignored local config.

- Q: Should CI run Loki, browser, or destructive tests?
- A: No. CI runs `uv run pytest -m "not loki and not browser and not destructive"` because GitHub Actions cannot reach the local Windows Plex server and must not require secrets.

- Q: How are smart TV and other client behaviors covered without every device present?
- A: The simulated harness models Plex Web, Roku, Apple TV, Android TV/Fire TV, Chromecast, Samsung Tizen, LG webOS, consoles, mobile, Plex HTPC, relay, and unknown clients. Real devices can be added as follow-up proof, but deterministic simulated coverage comes first.
