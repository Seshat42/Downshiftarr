# WSL Development Runbook

Use WSL as the primary development path for Downshiftarr. The Windows checkout is
`C:\Users\D3\Documents\Downshiftarr`; the matching WSL path is
`/mnt/c/Users/D3/Documents/Downshiftarr`.

## Primary Path

```bash
cd /mnt/c/Users/D3/Documents/Downshiftarr
git status --short --branch
git remote -v
```

Work from the existing checkout unless the lane explicitly says otherwise. This
workspace is shared, so inspect status before editing and never revert unrelated
changes.

## Remote Storage

GitHub is used only as the `origin` remote for repository storage. Do not rely on any remote platform
feature beyond plain Git fetch and push.

Use plain Git remote-storage checks when needed:

```bash
git remote -v
git ls-remote origin HEAD
git fetch --prune origin
```

## uv Setup

This repository carries `pyproject.toml` and `uv.lock`. Bootstrap with the
locked project environment:

```bash
cd /mnt/c/Users/D3/Documents/Downshiftarr
uv sync --all-groups
uv run pytest -m "not loki and not browser and not destructive"
```

## Verification Commands

Run the focused proof first, then broaden before closeout:

```bash
python scripts/testing/verify_local.py
```

For docs-only lanes, at minimum verify repository state and the intended file
scope:

```bash
git status --short
git diff -- docs/development/wsl.md
```

## Branch Intake

During bootstrap, branch intake is review-only unless the user explicitly opens
the merge lane.

```bash
git branch --show-current
git branch --all
git fetch --all --prune
git branch --all --format='%(refname:short)'
git log --oneline --decorate --graph --all --max-count=40
```

Before touching a branch, record the current branch, uncommitted files, and
whether the branch has a remote tracking branch. Do not merge during bootstrap.

## Case-Sensitive Filename Collisions

Windows is usually case-insensitive while WSL can operate in case-sensitive
contexts. Check for names that differ only by case before branch intake or broad
renames:

```bash
git ls-files | awk '{ lower=tolower($0); seen[lower]++; names[lower]=names[lower] "\n  " $0 } END { for (path in seen) if (seen[path] > 1) print path names[path] }'
```

The initial checkout had both root `test_downshiftarr.py` and `test_Downshiftarr.py` entries, which collided on the
Windows-backed path. Bootstrap moved their coverage into unique lowercase files under `tests/`. Do not recreate
case-only filename variants on this workspace.

## No-Merge Bootstrap Boundary

Bootstrap work may fetch, inspect, document, and test. It must not merge feature
branches into `main`, rebase shared branches, or normalize concurrent edits.
Consolidation into a single `main` is a separate deliberate phase with recorded
branch state, conflicts, and verification.
