# Downshiftarr Branch Intake Inventory

Bootstrap date: 2026-05-28  
Repository: `Seshat42/Downshiftarr`  
Default branch: `main`  
Inventory scope: historical branch intake plus final single-main consolidation cleanup record. Intake did not authorize merges; the later 2026-05-28 consolidation phase was explicitly authorized by the user.

## Intake Summary

- Local branches: 12
- GitHub branches: 12
- Local remote-tracking branches: 12, excluding `origin/HEAD`
- Current checkout during intake: `main` at `2b3cfa0`
- GitHub branch protection: none reported by the branch API for the listed branches
- Open PRs found: 8
- Merged PRs found: 6
- Open issues found: 1
- Worktree note: the initial checkout exposed a Windows case-insensitive filename collision between root tests
  `test_Downshiftarr.py` and `test_downshiftarr.py`. Bootstrap resolved that by moving their coverage into unique
  lowercase files under `tests/`; this was not a branch merge.

Relationship columns use `behind/ahead` counts against the named comparison branch.

## Branch Inventory

| Branch | SHA | vs `main` | vs `dev` | Upstream / remote | PR / issue state | Intake note |
| --- | --- | ---: | ---: | --- | --- | --- |
| `main` | `2b3cfa0` | `0/0` | `2/11` | `origin/main` | Default branch | Baseline for this intake. |
| `dev` | `78a13bf` | `11/2` | `0/0` | `origin/dev` | PR #2 merged into `main` | Stale integration branch; compare intent before reuse. |
| `add-tests-media-height-4449859519764339005` | `4f6031e` | `9/1` | `2/3` | `origin/add-tests-media-height-4449859519764339005` | PR #9 open to `main` | Test-only candidate; needs conflict/test review before consolidation. |
| `fix-plex-token-exposure-14819038041623419576` | `30c0957` | `9/1` | `2/3` | `origin/fix-plex-token-exposure-14819038041623419576` | PR #10 open to `main` | Security-sensitive candidate; prioritize review and regression testing. |
| `fix-unused-annotations-import-14675292598164734863` | `bca35e2` | `9/1` | `2/3` | `origin/fix-unused-annotations-import-14675292598164734863` | PR #11 open to `main` | Small cleanup candidate; verify no dependency on later branches. |
| `jules-10351953059055018286-c854910a` | `46e5dff` | `9/1` | `2/3` | `origin/jules-10351953059055018286-c854910a` | PR #12 open to `main` | Test coverage candidate for dynamic range classification. |
| `jules-16002624577278156886-445e8c56` | `876facd` | `9/1` | `2/3` | `origin/jules-16002624577278156886-445e8c56` | PR #8 open to `main` | Test coverage candidate for `safe_int`. |
| `jules-311580304402418888-ae638ed7` | `db427f5` | `9/1` | `2/3` | `origin/jules-311580304402418888-ae638ed7` | PR #14 open to `main` | Test coverage candidate for `env_bool`. |
| `jules-8496729870724669652-24d2ecea` | `607e8f4` | `9/1` | `2/3` | `origin/jules-8496729870724669652-24d2ecea` | PR #7 open to `main` | Test coverage candidate for quality classification. |
| `optimize-session-search-early-exit-10951549358986469248` | `60e9dd1` | `8/0` | `2/3` | `origin/optimize-session-search-early-exit-10951549358986469248` | PR #4 merged to `main` | Appears already integrated; archive/delete only in a later approved cleanup phase. |
| `test-normalize-decision-8116256256308464572` | `6e30d8f` | `8/0` | `2/3` | `origin/test-normalize-decision-8116256256308464572` | PR #6 merged to `main` | Appears already integrated; archive/delete only in a later approved cleanup phase. |
| `testing-improvement-parse-resolution-hint-11289850538183556530` | `defebf4` | `9/1` | `2/3` | `origin/testing-improvement-parse-resolution-hint-11289850538183556530` | PR #5 open to `main` | Test coverage candidate for resolution parsing. |

## GitHub PR And Issue Snapshot

Open PRs targeting `main`:

- #5 `testing-improvement-parse-resolution-hint-11289850538183556530`: Add unit tests for resolution parsing functions.
- #7 `jules-8496729870724669652-24d2ecea`: Add tests for `is_high_quality`.
- #8 `jules-16002624577278156886-445e8c56`: Add tests for `safe_int`.
- #9 `add-tests-media-height-4449859519764339005`: Test `media_height` fallback behavior.
- #10 `fix-plex-token-exposure-14819038041623419576`: Move Plex token from URL query to HTTP headers.
- #11 `fix-unused-annotations-import-14675292598164734863`: Remove unused future annotations import.
- #12 `jules-10351953059055018286-c854910a`: Add tests for `classify_dynamic_range`.
- #14 `jules-311580304402418888-ae638ed7`: Add tests for `env_bool`.

Merged PRs visible through `gh`:

- #1 `Seshat42-patch-1` into `dev`.
- #2 `dev` into `main`.
- #4 `optimize-session-search-early-exit-10951549358986469248` into `main`.
- #6 `test-normalize-decision-8116256256308464572` into `main`.
- #13 `jules-3957427238692128982-da9cb7f1` into `main`; source branch no longer present locally or on GitHub.
- #15 `jules-5365658014767378923-5ad26d80` into `main`; source branch no longer present locally or on GitHub.

Open issues:

- #3: `possibility of docker container?`

## Consolidation Plan Notes (Superseded)

These notes governed the handoff from bootstrap into the now-completed consolidation record below.

- Preserve the no-merge policy until each open PR is rebased or otherwise reviewed against current `main`.
- Review PR #10 first because it changes token handling and has the highest security impact.
- Batch the test-only PRs after confirming they do not overlap or duplicate already-merged coverage from PRs #13 and #15.
- Treat `dev` as historical/stale until its two commits ahead of `main` are inspected and either recovered, superseded, or intentionally retired.
- Merged branch refs #4 and #6 are cleanup candidates only after branch retention policy and remote deletion authority are explicitly confirmed.
- Issue #3 should be routed separately from branch consolidation because Docker packaging can create product/runtime policy decisions beyond branch hygiene.

## Single-Main Consolidation Record

Consolidation date: 2026-05-28  
Temporary branch: `codex/consolidate-all-branches`  
Starting commit: local `main` at `9749e87` (`chore: bootstrap Downshiftarr office`)  
Remote baseline verified before merging: `origin/main` at `2b3cfa0`

The user explicitly authorized this phase after bootstrap: merge all branch and PR content into one `main`, push to GitHub, clear open PRs, and delete every non-`main` remote branch.

Merged content:

| Source | PR | Merge commit | Final disposition |
| --- | ---: | --- | --- |
| `dev` | n/a | `032d710` | Included newer shim and README shim docs; security-adjusted shim token transport to headers. |
| `fix-plex-token-exposure-14819038041623419576` | #10 | `adee13c` | Included header-based Plex token transport in `Downshiftarr.py` and preserved the equivalent shim behavior. |
| `fix-unused-annotations-import-14675292598164734863` | #11 | `2849525` | Included import cleanup in `Downshiftarr.py`. |
| `add-tests-media-height-4449859519764339005` | #9 | `39580ee` | Ported tests to `tests/test_media_height.py`. |
| `jules-8496729870724669652-24d2ecea` | #7 | `3b04a2b` | Ported `is_high_quality` tests to `tests/test_quality_classification.py`. |
| `jules-10351953059055018286-c854910a` | #12 | `deae9ec` | Ported `classify_dynamic_range` tests to `tests/test_quality_classification.py`. |
| `jules-16002624577278156886-445e8c56` | #8 | `d2c38d8` | Ported `safe_int` tests to `tests/test_helpers.py`. |
| `testing-improvement-parse-resolution-hint-11289850538183556530` | #5 | `92e2552` | Ported helper parsing tests to `tests/test_helpers.py`; dropped generated cache/log artifacts. |
| `jules-311580304402418888-ae638ed7` | #14 | `fc0045a` | Ported `env_bool` tests to `tests/test_helpers.py`. |

Already-integrated branches `optimize-session-search-early-exit-10951549358986469248` and `test-normalize-decision-8116256256308464572` remain cleanup-only branches. They should be deleted with the other non-`main` remote refs after `origin/main` contains the consolidation.

Post-push cleanup:

- `main` was pushed to GitHub at `6c70c39`.
- GitHub automatically marked PRs #5, #7, #8, #9, #10, #11, #12, and #14 as merged at 2026-05-28 05:37:55 UTC because their head commits are ancestors of `main`.
- Open PR queue after push: empty.
- Remote branches were ancestry-verified against `origin/main` before deletion.
- Deleted remote refs: `add-tests-media-height-4449859519764339005`, `dev`, `fix-plex-token-exposure-14819038041623419576`, `fix-unused-annotations-import-14675292598164734863`, `jules-10351953059055018286-c854910a`, `jules-16002624577278156886-445e8c56`, `jules-311580304402418888-ae638ed7`, `jules-8496729870724669652-24d2ecea`, `optimize-session-search-early-exit-10951549358986469248`, `test-normalize-decision-8116256256308464572`, and `testing-improvement-parse-resolution-hint-11289850538183556530`.
- Final GitHub branch list after cleanup: `main` only.
