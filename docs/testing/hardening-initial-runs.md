# Downshiftarr Hardening Initial Runs

Last reviewed: 2026-06-01

This is the durable manual checklist requested for the setup-only phase. Do not treat these as already-run proof. Run one lane at a time, record the seed/profile/output, then enhance coverage based on findings.

All commands are WSL-first. Use `UV_LINK_MODE=copy uv run --locked` for the outer project command so the Windows-backed checkout does not emit hardlink warnings or mutate the lockfile during hardening proof. The native Atheris runner still launches the fuzz target internally with isolated Python 3.11.

## Setup Verification

```bash
UV_LINK_MODE=copy uv run --locked python scripts/testing/verify_hardening_setup.py
UV_LINK_MODE=copy uv run --locked python scripts/testing/list_hardening_runs.py --check
```

## Boundary Value Analysis

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked pytest -m boundary
```

Bounded first pass:

```bash
UV_LINK_MODE=copy uv run --locked pytest -m boundary -q
```

Enhance after first run: add rows for any new threshold, malformed value, or off-by-one behavior found by the other hardening lanes.

## Property-Based Testing

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked pytest -m property
```

Bounded first pass:

```bash
UV_LINK_MODE=copy uv run --locked pytest -m property --hypothesis-profile=hardening -q
```

Enhance after first run: promote each minimized counterexample into a named regression test before widening strategies.

## Python-Level Fuzz Testing

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked pytest -m fuzz
```

Bounded first pass:

```bash
UV_LINK_MODE=copy uv run --locked pytest -m fuzz --hypothesis-profile=hardening -q
```

Enhance after first run: grow strategies toward uncovered parser branches, unusual Unicode, malformed metadata, and token-redaction edges.

## Native Atheris Fuzz Testing

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked python scripts/testing/run_native_fuzz.py --list-targets
```

Shim-first extended first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_native_fuzz.py --target shim-parsers --runs 100000 --max-total-time 300 --run
```

Next target:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_native_fuzz.py --target downshiftarr-parsers --runs 1000 --max-total-time 30 --run
```

Enhance after first run: preserve only redacted/minimized crash inputs, then add them as deterministic tests.

## Monkey Testing

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked python scripts/testing/run_monkey.py --list-scenarios
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_monkey.py --scenario client-event-matrix --seed 424242 --iterations 250 --run
```

Next scenarios:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_monkey.py --scenario accessory-noop --seed 424242 --iterations 250 --run
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_monkey.py --scenario fallback-selection --seed 424242 --iterations 250 --run
```

Enhance after first run: save failing seeds as regression tests and add client-profile-specific cases for any repeated failure family.

## Chaos Testing

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked python scripts/testing/run_chaos.py --list-scenarios
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_chaos.py --scenario fake-service-faults --seed 515151 --iterations 100 --run
```

Next scenarios:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_chaos.py --scenario client-control-faults --seed 515151 --iterations 100 --run
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_chaos.py --scenario malformed-metadata --seed 515151 --iterations 100 --run
```

Enhance after first run: add a scenario for each new fake Plex/Tautulli/client failure mode before considering any Loki destructive variant.

## Mutation Testing

List/setup command:

```bash
UV_LINK_MODE=copy uv run --locked python scripts/testing/run_mutation.py --list-targets
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python scripts/testing/run_mutation.py --target downshiftarr-core --run
```

Review previous local results:

```bash
UV_LINK_MODE=copy uv run --locked python scripts/testing/run_mutation.py --target downshiftarr-core-results --dry-run
```

Enhance after first run: triage surviving mutants, add focused tests, and rerun the same target before broadening mutation scope.
