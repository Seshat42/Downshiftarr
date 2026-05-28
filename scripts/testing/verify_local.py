#!/usr/bin/env python3
"""Run Downshiftarr's official local verification gates."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOKEN_QUERY_PATTERNS = (
    re.compile(r"[?&](?:X-Plex-Token|PLEX_TOKEN|token)="),
    re.compile(r"X-Plex-Token\s*="),
)


@dataclass(frozen=True)
class Gate:
    name: str
    command: list[str]


def resolve_gitleaks_bin() -> str:
    return os.environ.get("GITLEAKS_BIN") or "gitleaks"


def missing_required_tools(gitleaks_bin: str | None = None) -> list[str]:
    required = ["git", "uv", gitleaks_bin or resolve_gitleaks_bin()]
    missing = []
    for tool in required:
        if shutil.which(tool) is None:
            missing.append(Path(tool).name)
    return missing


def build_gates(python_version: str = "3.12", gitleaks_bin: str | None = None) -> list[Gate]:
    gitleaks = gitleaks_bin or resolve_gitleaks_bin()
    return [
        Gate("status", ["git", "status", "--short", "--branch", "--untracked-files=all"]),
        Gate("sync", ["uv", "sync", "--all-groups", "--python", python_version, "--locked"]),
        Gate("tests-non-destructive", ["uv", "run", "--locked", "pytest", "-m", "not loki and not browser and not destructive"]),
        Gate("tests-simulated", ["uv", "run", "--locked", "pytest", "-m", "simulated"]),
        Gate("tests-media", ["uv", "run", "--locked", "pytest", "-m", "media"]),
        Gate("ruff-check", ["uv", "run", "--locked", "ruff", "check", "."]),
        Gate("ruff-format", ["uv", "run", "--locked", "ruff", "format", "--check", "."]),
        Gate("pip-audit", ["uv", "run", "--locked", "pip-audit"]),
        Gate(
            "bandit",
            [
                "uv",
                "run",
                "--locked",
                "bandit",
                "-c",
                "pyproject.toml",
                "-r",
                "Downshiftarr.py",
                "Plex Transcoder",
                "--baseline",
                "docs/security/bandit-baseline.json",
            ],
        ),
        Gate("gitleaks", [gitleaks, "detect", "--source", ".", "--config", ".gitleaks.toml", "--no-banner", "--redact"]),
        Gate("plex-token-query-static-check", [sys.executable, str(Path(__file__).relative_to(REPO_ROOT)), "--static-token-check-only"]),
        Gate("diff-check", ["git", "diff", "--check"]),
    ]


def source_paths() -> list[Path]:
    paths = [REPO_ROOT / "Downshiftarr.py", REPO_ROOT / "Plex Transcoder"]
    paths.extend((REPO_ROOT / "scripts").rglob("*.py"))
    return paths


def run_static_token_check() -> int:
    findings = []
    for path in source_paths():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in TOKEN_QUERY_PATTERNS):
                findings.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{line.strip()}")

    if findings:
        print("Plex token query-string construction found:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1

    print("No Plex token query-string construction found in source scripts.")
    return 0


def run_gate(gate: Gate) -> int:
    print(f"\n==> {gate.name}: {' '.join(gate.command)}", flush=True)
    completed = subprocess.run(gate.command, cwd=REPO_ROOT)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="3.12", help="Python version passed to uv sync.")
    parser.add_argument("--static-token-check-only", action="store_true", help="Run only the Plex token transport static check.")
    args = parser.parse_args(argv)

    if args.static_token_check_only:
        return run_static_token_check()

    missing = missing_required_tools()
    if missing:
        print("Missing required local verification tool(s): " + ", ".join(missing), file=sys.stderr)
        print("Install them locally or set GITLEAKS_BIN to an executable gitleaks path.", file=sys.stderr)
        return 127

    for gate in build_gates(python_version=args.python):
        result = run_gate(gate)
        if result != 0:
            print(f"Local verification failed at gate: {gate.name}", file=sys.stderr)
            return result

    print("\nLocal verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
