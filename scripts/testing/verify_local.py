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
DEFAULT_EXCLUDED_MARKERS = (
    "loki",
    "browser",
    "destructive",
    "property",
    "fuzz",
    "native_fuzz",
    "monkey",
    "chaos",
    "mutation",
    "boundary",
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


def non_destructive_marker_expression() -> str:
    return " and ".join(f"not {marker}" for marker in DEFAULT_EXCLUDED_MARKERS)


def build_gates(
    python_version: str = "3.12",
    gitleaks_bin: str | None = None,
    ci: bool = False,
    hardening_setup: bool = False,
) -> list[Gate]:
    gitleaks = gitleaks_bin or resolve_gitleaks_bin()
    gates = [
        Gate("status", ["git", "status", "--short", "--branch", "--untracked-files=all"]),
        Gate("sync", ["uv", "sync", "--all-groups", "--python", python_version, "--locked"]),
        Gate("tests-non-destructive", ["uv", "run", "--locked", "pytest", "-m", non_destructive_marker_expression()]),
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
    ]
    if ci:
        gates.append(Gate("secret-hygiene", [sys.executable, "scripts/testing/verify_secret_hygiene.py"]))
    if hardening_setup:
        gates.append(Gate("hardening-setup", [sys.executable, "scripts/testing/verify_hardening_setup.py"]))
    gates.append(Gate("github-storage-only", [sys.executable, str(Path(__file__).relative_to(REPO_ROOT)), "--storage-only-check-only"]))
    gates.append(Gate("diff-check", ["git", "diff", "--check"]))
    return gates


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


def remote_branch_names() -> list[str]:
    completed = subprocess.run(
        ["git", "branch", "-r", "--format=%(refname:short)"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git branch -r failed")
    return sorted(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip() and line.strip() != "origin" and not line.strip().endswith("/HEAD")
    )


def tracked_github_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--", ".github"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git ls-files .github failed")
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def run_storage_only_check() -> int:
    findings: list[str] = []
    github_dir = REPO_ROOT / ".github"
    if github_dir.exists():
        findings.append(".github directory must be absent; GitHub is storage only")

    tracked_github = tracked_github_paths()
    if tracked_github:
        findings.append("tracked .github paths remain: " + ", ".join(tracked_github))

    non_main_remotes = [branch for branch in remote_branch_names() if branch != "origin/main"]
    if non_main_remotes:
        findings.append("non-main remote branches present: " + ", ".join(non_main_remotes))

    docs_paths = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "POSTERITY.md",
        REPO_ROOT / "README.md",
    ]
    if (REPO_ROOT / "docs").exists():
        docs_paths.extend(sorted((REPO_ROOT / "docs").rglob("*.md")))

    docs_with_github_ci_authority: list[str] = []
    for path in docs_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?i)(github\s+(?:actions|ci|security ci|code scanning|daily release|release publication)|\bCI mirror\b)", text):
            docs_with_github_ci_authority.append(str(path.relative_to(REPO_ROOT)))
    if docs_with_github_ci_authority:
        findings.append("GitHub CI/release authority wording remains: " + ", ".join(docs_with_github_ci_authority))

    if findings:
        print("GitHub storage-only policy failed:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1

    print("GitHub storage-only policy passed: no .github directory and origin/main is the only remote branch.")
    return 0


def run_gate(gate: Gate) -> int:
    print(f"\n==> {gate.name}: {' '.join(gate.command)}", flush=True)
    completed = subprocess.run(gate.command, cwd=REPO_ROOT)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="3.12", help="Python version passed to uv sync.")
    parser.add_argument("--ci", action="store_true", help="Legacy alias for local extra hygiene; does not imply GitHub CI authority.")
    parser.add_argument("--hardening-setup", action="store_true", help="Verify hardening setup without running hardening campaigns.")
    parser.add_argument("--static-token-check-only", action="store_true", help="Run only the Plex token transport static check.")
    parser.add_argument("--storage-only-check-only", action="store_true", help="Run only the local GitHub storage-only policy check.")
    args = parser.parse_args(argv)

    if args.static_token_check_only:
        return run_static_token_check()
    if args.storage_only_check_only:
        return run_storage_only_check()

    missing = missing_required_tools()
    if missing:
        print("Missing required local verification tool(s): " + ", ".join(missing), file=sys.stderr)
        print("Install them locally or set GITLEAKS_BIN to an executable gitleaks path.", file=sys.stderr)
        return 127

    for gate in build_gates(python_version=args.python, ci=args.ci, hardening_setup=args.hardening_setup):
        result = run_gate(gate)
        if result != 0:
            print(f"Local verification failed at gate: {gate.name}", file=sys.stderr)
            return result

    print("\nLocal verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
