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
