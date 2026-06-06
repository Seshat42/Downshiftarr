#!/usr/bin/env python3
"""Shared catalog for manual Downshiftarr hardening test runs."""

from __future__ import annotations

import os
from dataclasses import dataclass

REQUIRED_CATEGORIES = ("boundary", "property", "fuzz", "native_fuzz", "monkey", "chaos", "mutation")
SECRET_ENV_KEYS = (
    "PLEX_TOKEN",
    "PLEX_USER_TOKEN",
    "TAUTULLI_APIKEY",
    "DOWNSHIFTARR_LOKI_PLEX_TOKEN",
    "DOWNSHIFTARR_TAUTULLI_APIKEY",
)


@dataclass(frozen=True)
class HardeningRun:
    category: str
    name: str
    description: str
    list_command: str
    first_pass_command: str
    enhancement_note: str


_RUNS = (
    HardeningRun(
        category="boundary",
        name="boundary-values",
        description="Explicit threshold and malformed-value checks for parsing, media policy, and token-safe URL handling.",
        list_command="UV_LINK_MODE=copy uv run --locked pytest -m boundary",
        first_pass_command="UV_LINK_MODE=copy uv run --locked pytest -m boundary -q",
        enhancement_note="Add new boundary rows for every bug found by fuzz, monkey, chaos, or mutation campaigns.",
    ),
    HardeningRun(
        category="property",
        name="property-invariants",
        description="Hypothesis-generated invariants for parsers, dynamic range classification, fallback selection, and shim rewrites.",
        list_command="UV_LINK_MODE=copy uv run --locked pytest -m property",
        first_pass_command="UV_LINK_MODE=copy uv run --locked pytest -m property --hypothesis-profile=hardening -q",
        enhancement_note="Promote any minimized counterexample into a named unit or boundary regression.",
    ),
    HardeningRun(
        category="fuzz",
        name="python-fuzz",
        description="Pytest-level fuzz/generative tests for hostile strings, metadata dictionaries, and transcoder arg vectors.",
        list_command="UV_LINK_MODE=copy uv run --locked pytest -m fuzz",
        first_pass_command="UV_LINK_MODE=copy uv run --locked pytest -m fuzz --hypothesis-profile=hardening -q",
        enhancement_note="Grow strategies toward any parser branch or log sanitizer that remains unexercised.",
    ),
    HardeningRun(
        category="native_fuzz",
        name="atheris-targets",
        description="Atheris/libFuzzer entrypoints for parser, metadata, and shim argument-rewrite surfaces.",
        list_command="UV_LINK_MODE=copy uv run --locked python scripts/testing/run_native_fuzz.py --list-targets",
        first_pass_command=(
            "DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python "
            "scripts/testing/run_native_fuzz.py --target shim-parsers --runs 100000 --max-total-time 300 --run"
        ),
        enhancement_note="Start with short seeded runs, then add corpora from minimized crashes only after redaction.",
    ),
    HardeningRun(
        category="monkey",
        name="client-event-monkey",
        description="Seeded fake Plex/Tautulli/client event sequences across the full simulated client profile registry.",
        list_command="UV_LINK_MODE=copy uv run --locked python scripts/testing/run_monkey.py --list-scenarios",
        first_pass_command=(
            "DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python "
            "scripts/testing/run_monkey.py --scenario client-event-matrix --seed 424242 --iterations 250 --run"
        ),
        enhancement_note="Save failing seeds as deterministic regression tests before increasing iteration counts.",
    ),
    HardeningRun(
        category="chaos",
        name="fake-service-chaos",
        description="Deterministic fake Plex/Tautulli fault injection for timeouts, malformed payloads, and fallback enforcement paths.",
        list_command="UV_LINK_MODE=copy uv run --locked python scripts/testing/run_chaos.py --list-scenarios",
        first_pass_command=(
            "DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python "
            "scripts/testing/run_chaos.py --scenario fake-service-faults --seed 515151 --iterations 100 --run"
        ),
        enhancement_note="Add a new chaos scenario for each external-service failure mode discovered in Loki testing.",
    ),
    HardeningRun(
        category="mutation",
        name="mutmut-campaign",
        description="mutmut campaign setup against the Python enforcement core, with reports kept local and ignored.",
        list_command="UV_LINK_MODE=copy uv run --locked python scripts/testing/run_mutation.py --list-targets",
        first_pass_command=(
            "DOWNSHIFTARR_HARDENING_MANUAL=1 UV_LINK_MODE=copy uv run --locked python "
            "scripts/testing/run_mutation.py --target downshiftarr-core --run"
        ),
        enhancement_note="Review surviving mutants and add focused tests before rerunning the same target.",
    ),
)


def all_runs() -> tuple[HardeningRun, ...]:
    return _RUNS


def redact_secrets(text: str) -> str:
    redacted = str(text)
    secrets = []
    for key in SECRET_ENV_KEYS:
        value = os.environ.get(key)
        if value and len(value) >= 4:
            secrets.append(value)
    for secret in sorted(set(secrets), key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def validate_catalog() -> list[str]:
    issues: list[str] = []
    categories = {run.category for run in _RUNS}
    missing = set(REQUIRED_CATEGORIES) - categories
    if missing:
        issues.append("Missing hardening categories: " + ", ".join(sorted(missing)))
    for run in _RUNS:
        if "DOWNSHIFTARR_HARDENING_MANUAL=1" not in run.first_pass_command and run.category in {
            "native_fuzz",
            "monkey",
            "chaos",
            "mutation",
        }:
            issues.append(f"{run.name} lacks the manual execution environment guard")
        if any(os.environ.get(key, "") and os.environ[key] in run.first_pass_command for key in SECRET_ENV_KEYS):
            issues.append(f"{run.name} includes a local secret in its command")
    return issues
