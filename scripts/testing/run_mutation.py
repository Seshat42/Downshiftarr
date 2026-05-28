#!/usr/bin/env python3
"""Manual mutmut runner for Downshiftarr."""

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
class MutationTarget:
    name: str
    description: str
    command: tuple[str, ...]


TARGETS = (
    MutationTarget(
        name="downshiftarr-core",
        description="Mutate the Python enforcement core configured in pyproject.toml.",
        command=("uv", "run", "--locked", "mutmut", "run"),
    ),
    MutationTarget(
        name="downshiftarr-core-results",
        description="Show mutmut results from the last local campaign.",
        command=("uv", "run", "--locked", "mutmut", "results"),
    ),
)


def target_names() -> list[str]:
    return [target.name for target in TARGETS]


def find_target(name: str) -> MutationTarget:
    for target in TARGETS:
        if target.name == name:
            return target
    raise KeyError(name)


def print_targets() -> None:
    for target in TARGETS:
        print(f"{target.name}: {target.description}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-targets", action="store_true", help="List mutation targets and exit.")
    parser.add_argument("--target", choices=target_names(), help="Mutation target to prepare or run.")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without running it.")
    parser.add_argument("--run", action="store_true", help="Actually run the selected mutmut target.")
    args = parser.parse_args(argv)

    if args.list_targets or not args.target:
        print_targets()
        return 0

    target = find_target(args.target)
    print(redact_secrets("Prepared mutation command:\n  " + " ".join(target.command)))
    if args.dry_run or not args.run:
        print("Dry run only. Set DOWNSHIFTARR_HARDENING_MANUAL=1 and pass --run to execute.")
        return 0
    if os.environ.get(MANUAL_ENV) != "1":
        print(f"Refusing to run mutation testing without {MANUAL_ENV}=1.", file=sys.stderr)
        return 2

    (REPO_ROOT / "artifacts" / "hardening" / "mutmut").mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(list(target.command), cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
