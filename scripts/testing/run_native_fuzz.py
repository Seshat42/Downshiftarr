#!/usr/bin/env python3
"""Manual Atheris/native fuzz runner for Downshiftarr."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.testing.hardening_catalog import redact_secrets

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_ENV = "DOWNSHIFTARR_HARDENING_MANUAL"


@dataclass(frozen=True)
class FuzzTarget:
    name: str
    path: str
    description: str


TARGETS = (
    FuzzTarget(
        name="downshiftarr-parsers",
        path="tests/fuzz_targets/fuzz_downshiftarr_parsers.py",
        description="Fuzz Downshiftarr parser, decision, dynamic-range, and media-height helpers.",
    ),
    FuzzTarget(
        name="shim-parsers",
        path="tests/fuzz_targets/fuzz_shim_parsers.py",
        description="Fuzz Plex Transcoder parser, stream-index, input-selection, and filter-rewrite helpers.",
    ),
)


def target_names() -> list[str]:
    return [target.name for target in TARGETS]


def find_target(name: str) -> FuzzTarget:
    for target in TARGETS:
        if target.name == name:
            return target
    raise KeyError(name)


def build_command(target: FuzzTarget, runs: int, max_total_time: int) -> list[str]:
    return [
        "uv",
        "run",
        "--isolated",
        "--python",
        "3.11",
        "--group",
        "native-fuzz",
        "python",
        target.path,
        f"-runs={runs}",
        f"-max_total_time={max_total_time}",
        "-artifact_prefix=artifacts/hardening/atheris/",
    ]


def print_targets() -> None:
    for target in TARGETS:
        print(f"{target.name}: {target.description}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-targets", action="store_true", help="List fuzz targets and exit.")
    parser.add_argument("--target", choices=target_names(), help="Fuzz target to prepare or run.")
    parser.add_argument("--runs", type=int, default=1000, help="Bounded libFuzzer run count for a first pass.")
    parser.add_argument("--max-total-time", type=int, default=30, help="Bounded libFuzzer wall time in seconds.")
    parser.add_argument("--run", action="store_true", help="Actually run the target; otherwise print the command only.")
    args = parser.parse_args(argv)

    if args.list_targets or not args.target:
        print_targets()
        return 0

    target = find_target(args.target)
    command = build_command(target, runs=max(1, args.runs), max_total_time=max(1, args.max_total_time))
    print(redact_secrets("Prepared native fuzz command:\n  " + " ".join(command)))

    if not args.run:
        print("Dry run only. Set DOWNSHIFTARR_HARDENING_MANUAL=1 and pass --run to execute.")
        return 0
    if os.environ.get(MANUAL_ENV) != "1":
        print(f"Refusing to run native fuzzing without {MANUAL_ENV}=1.", file=sys.stderr)
        return 2

    (REPO_ROOT / "artifacts" / "hardening" / "atheris").mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
