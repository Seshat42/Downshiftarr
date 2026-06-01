#!/usr/bin/env python3
"""Verify Downshiftarr hardening-test setup without running campaigns."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPO_ROOT = Path(__file__).resolve().parents[2]
HARDENING_MARKER_EXPR = "property or fuzz or native_fuzz or monkey or chaos or mutation or boundary"
IGNORED_OUTPUTS = (".hypothesis/", ".mutmut-cache/", "artifacts/hardening/")


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]


def missing_required_tools() -> list[str]:
    return [tool for tool in ("git", "uv") if shutil.which(tool) is None]


def native_fuzz_setup_check() -> Check:
    if sys.platform.startswith("win"):
        return Check("native-fuzz-target-list-windows", [sys.executable, "scripts/testing/run_native_fuzz.py", "--list-targets"])
    return Check(
        "atheris-python311-import",
        [
            "uv",
            "run",
            "--isolated",
            "--python",
            "3.11",
            "--group",
            "native-fuzz",
            "python",
            "-c",
            "import atheris; print('atheris ok')",
        ],
    )


def build_checks() -> list[Check]:
    return [
        Check("hardening-run-list", [sys.executable, "scripts/testing/list_hardening_runs.py", "--check"]),
        Check("hardening-pytest-collect", ["uv", "run", "--locked", "pytest", "--collect-only", "-q", "-m", HARDENING_MARKER_EXPR]),
        native_fuzz_setup_check(),
        Check("mutmut-import", ["uv", "run", "--locked", "python", "-c", "import mutmut; print('mutmut ok')"]),
    ]


def verify_ignored_outputs() -> int:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [entry for entry in IGNORED_OUTPUTS if entry not in gitignore]
    if missing:
        print("Hardening output paths missing from .gitignore: " + ", ".join(missing), file=sys.stderr)
        return 1
    print("Hardening output paths are ignored.")
    return 0


def run_check(check: Check) -> int:
    print(f"\n==> {check.name}: {' '.join(check.command)}", flush=True)
    completed = subprocess.run(check.command, cwd=REPO_ROOT)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List setup checks without running them.")
    args = parser.parse_args(argv)

    checks = build_checks()
    if args.list:
        for check in checks:
            print(f"{check.name}: {' '.join(check.command)}")
        print("ignored-outputs: internal .gitignore validation")
        return 0

    missing = missing_required_tools()
    if missing:
        print("Missing required hardening setup tool(s): " + ", ".join(missing), file=sys.stderr)
        return 127

    for check in checks:
        result = run_check(check)
        if result != 0:
            print(f"Hardening setup verification failed at check: {check.name}", file=sys.stderr)
            return result

    ignored_result = verify_ignored_outputs()
    if ignored_result != 0:
        return ignored_result

    print("\nHardening setup verification passed. No fuzz, monkey, chaos, or mutation campaigns were run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
