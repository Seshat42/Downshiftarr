# Downshiftarr Hardening Initial Runs

Last reviewed: 2026-05-28

This is the durable manual checklist requested for the setup-only phase. Do not treat these as already-run proof. Run one lane at a time, record the seed/profile/output, then enhance coverage based on findings.

## Setup Verification

```bash
python scripts/testing/verify_hardening_setup.py
python scripts/testing/list_hardening_runs.py --check
```

## Boundary Value Analysis

List/setup command:

```bash
uv run pytest -m boundary
```

Bounded first pass:

```bash
uv run pytest -m boundary -q
```

Enhance after first run: add rows for any new threshold, malformed value, or off-by-one behavior found by the other hardening lanes.

## Property-Based Testing

List/setup command:

```bash
uv run pytest -m property
```

Bounded first pass:

```bash
uv run pytest -m property --hypothesis-profile=hardening -q
```

Enhance after first run: promote each minimized counterexample into a named regression test before widening strategies.

## Python-Level Fuzz Testing

List/setup command:

```bash
uv run pytest -m fuzz
```

Bounded first pass:

```bash
uv run pytest -m fuzz --hypothesis-profile=hardening -q
```

Enhance after first run: grow strategies toward uncovered parser branches, unusual Unicode, malformed metadata, and token-redaction edges.

## Native Atheris Fuzz Testing

List/setup command:

```bash
uv run --python 3.11 python scripts/testing/run_native_fuzz.py --list-targets
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run --python 3.11 python scripts/testing/run_native_fuzz.py --target downshiftarr-parsers --runs 1000 --max-total-time 30 --run
```

Next target:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run --python 3.11 python scripts/testing/run_native_fuzz.py --target shim-parsers --runs 1000 --max-total-time 30 --run
```

Enhance after first run: preserve only redacted/minimized crash inputs, then add them as deterministic tests.

## Monkey Testing

List/setup command:

```bash
uv run python scripts/testing/run_monkey.py --list-scenarios
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_monkey.py --scenario client-event-matrix --seed 424242 --iterations 250 --run
```

Next scenarios:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_monkey.py --scenario accessory-noop --seed 424242 --iterations 250 --run
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_monkey.py --scenario fallback-selection --seed 424242 --iterations 250 --run
```

Enhance after first run: save failing seeds as regression tests and add client-profile-specific cases for any repeated failure family.

## Chaos Testing

List/setup command:

```bash
uv run python scripts/testing/run_chaos.py --list-scenarios
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_chaos.py --scenario fake-service-faults --seed 515151 --iterations 100 --run
```

Next scenarios:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_chaos.py --scenario client-control-faults --seed 515151 --iterations 100 --run
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_chaos.py --scenario malformed-metadata --seed 515151 --iterations 100 --run
```

Enhance after first run: add a scenario for each new fake Plex/Tautulli/client failure mode before considering any Loki destructive variant.

## Mutation Testing

List/setup command:

```bash
uv run python scripts/testing/run_mutation.py --list-targets
```

Bounded first pass:

```bash
DOWNSHIFTARR_HARDENING_MANUAL=1 uv run python scripts/testing/run_mutation.py --target downshiftarr-core --run
```

Review previous local results:

```bash
uv run python scripts/testing/run_mutation.py --target downshiftarr-core-results --dry-run
```

Enhance after first run: triage surviving mutants, add focused tests, and rerun the same target before broadening mutation scope.
