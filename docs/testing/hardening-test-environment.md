# Downshiftarr Hardening Test Environment

Last reviewed: 2026-05-28

This document describes the setup-only hardening lanes for fuzz testing, property-based testing, monkey testing, chaos testing, mutation testing, and boundary value analysis. These lanes are manual by design: the setup verifier proves that the commands, markers, tools, and artifact hygiene are wired, but it does not launch long-running campaigns.

## Tooling

- Primary shell: WSL at `/mnt/c/Users/D3/Documents/Downshiftarr`.
- Normal project lane: Python 3.12 through `uv`.
- Native fuzz lane: Python 3.11 through `uv python install 3.11`, with Atheris/libFuzzer. Runner internals use isolated `uv` environments so this lane does not replace the normal Python 3.12 project venv.
- WSL build tools: `clang`, `llvm`, `build-essential`, and `pkg-config`.
- Python hardening tools: Hypothesis, Atheris, and mutmut.

Ubuntu in this workspace did not publish `python3.11` apt packages, so the Python 3.11 native-fuzz runtime is intentionally managed by `uv`. The WSL system packages provide the compiler/runtime pieces Atheris may need.

## Manual-Only Markers

- `boundary`: boundary value analysis.
- `property`: Hypothesis property-based invariants.
- `fuzz`: Python-level fuzz/generative pytest tests.
- `native_fuzz`: Atheris/libFuzzer targets through the Python 3.11 lane.
- `monkey`: seeded random fake Plex/Tautulli/client event tests.
- `chaos`: deterministic fake-service fault injection.
- `mutation`: mutmut setup and campaign targets.

The default local verification runner excludes these markers so hardening campaigns do not run accidentally:

```bash
python scripts/testing/verify_local.py
```

To verify setup without campaigns:

```bash
python scripts/testing/verify_hardening_setup.py
```

## Safety Controls

- Native fuzz, monkey, chaos, and mutation runners require `DOWNSHIFTARR_HARDENING_MANUAL=1` plus an explicit `--run` flag before they execute.
- Runner `--list-*` and dry-run modes are safe for setup verification.
- Hardening lanes use fakes and synthetic inputs only. They do not contact Loki, Tautulli, Plex Web, browser sessions, Docker sidecars, or external Plex servers.
- Secrets are redacted from runner output using known local secret environment variable names.
- Generated corpora, crashes, reports, and caches stay ignored under `.hypothesis/`, `.mutmut-cache/`, and `artifacts/hardening/`.

## Coverage Focus

- Parser and env helpers: `parse_resolution_hint`, `safe_int`, `env_bool`, `env_int`, `env_float`, and argument parsing.
- Media policy: height thresholds, dynamic-range classification, protected-source detection, fallback ranking, and malformed metadata.
- Plex client behavior: fake client discovery, direct play/stream no-ops, protected transcode downshift, missing client, remote-control failure, seek failure, and stale session lookup.
- Shim behavior: primary input discovery, stream index parsing, metadata normalization, fallback compatibility, and HDR tone-map filter rewriting.
- Security hygiene: no token query-string construction, no secret printing, and no hardening artifact leakage into tracked files or release inputs.

## Enhancement Loop

1. Run the bounded first-pass command for one hardening type from `docs/testing/hardening-initial-runs.md`.
2. Review failures, minimized examples, surviving mutants, or seeds.
3. Convert each confirmed issue into a deterministic unit, simulated, boundary, or regression test.
4. Fix the implementation only after the regression exists.
5. Re-run the same hardening command, then expand duration, examples, or iterations.
