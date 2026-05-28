# Downshiftarr Branch Consolidation Record

Last reviewed: 2026-05-28

This file preserves the branch-intake outcome while keeping branch policy separate from hosted automation.
GitHub is approved for repository storage, security CI, code scanning, secret protection, and daily releases.

## Current State

- Authoritative branch: `main`.
- Local branch policy: keep only `main` unless the user explicitly opens a temporary local work lane.
- Remote branch policy: keep only `origin/main`; tags may remain.
- Verification policy: use local WSL gates, especially `python scripts/testing/verify_local.py`; GitHub security CI mirrors these with `python scripts/testing/verify_local.py --ci`.

## Historical Intake Summary

- Bootstrap materialized the available remote branch refs locally and stopped before consolidation.
- A Windows case-insensitive filename collision between root test files was resolved by moving coverage under lowercase `tests/`.
- The user later authorized single-main consolidation.
- Content from the former development, security, cleanup, and test branches was folded into `main`.
- Non-main local and remote refs were removed after ancestry or supersession verification.
- The optional `Plex Transcoder` shim and `Downshiftarr.py` now use Plex token headers rather than query-string token transport.

## Preservation Notes

- Do not recreate root tests that differ only by case.
- Do not add remote platform features beyond the approved security CI, code scanning, secret protection, and daily release workflows without a fresh user decision.
- When branch history matters, use local Git evidence: `git log`, `git branch`, `git show`, and `git reflog` where available.
- When remote storage matters, use plain Git against `origin`: `git fetch`, `git push`, and `git ls-remote`.
