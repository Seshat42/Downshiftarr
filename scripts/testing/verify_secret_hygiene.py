#!/usr/bin/env python3
"""Fail when tracked source contains local secrets or private test artifacts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_SECRET_BASENAMES = {".env", "Downshiftarr.env", "Downshiftarr.test.env"}
FORBIDDEN_ARTIFACT_SEGMENTS = {
    ".venv",
    "__pycache__",
    "artifacts",
    "codex-security-scans",
    "htmlcov",
    "playwright-report",
    "security-scans",
    "test-results",
}
FORBIDDEN_DB_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
FORBIDDEN_BINARY_SUFFIXES = {".pyc", ".pyo"}
FORBIDDEN_SCAN_SUFFIXES = {".sarif"}
SCREENSHOT_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?P<name>PLEX_TOKEN|PLEX_USER_TOKEN|X-PLEX-TOKEN|TAUTULLI_APIKEY|TAUTULLI_API_KEY|API_KEY|APIKEY)\b"
    r"\s*[=:]\s*[\"']?(?P<value>[A-Za-z0-9_-]{20,})"
)
ALLOWED_VALUE_PREFIXES = ("PUT_YOUR_", "YOUR_")
ALLOWED_VALUE_FRAGMENTS = ("placeholder", "replace-with", "secret-token", "api-secret", "generated-key")


def tracked_files() -> list[str]:
    completed = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True, stdout=subprocess.PIPE)
    return [item for item in completed.stdout.decode("utf-8").split("\0") if item]


def path_segments(path: str) -> set[str]:
    return set(Path(path).parts)


def find_path_findings(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        parsed = Path(normalized)
        basename = parsed.name
        suffix = parsed.suffix.lower()
        segments = path_segments(normalized)

        if basename in FORBIDDEN_SECRET_BASENAMES:
            findings.append(f"forbidden local secret file: {normalized}")
        if segments & FORBIDDEN_ARTIFACT_SEGMENTS:
            findings.append(f"forbidden generated/local artifact path: {normalized}")
        if suffix in FORBIDDEN_BINARY_SUFFIXES:
            findings.append(f"forbidden bytecode file: {normalized}")
        if suffix in FORBIDDEN_DB_SUFFIXES:
            findings.append(f"forbidden local database file: {normalized}")
        if suffix in FORBIDDEN_SCAN_SUFFIXES:
            findings.append(f"forbidden local scan output: {normalized}")
        if suffix in SCREENSHOT_SUFFIXES or "screenshot" in normalized.lower():
            findings.append(f"forbidden screenshot/image proof path: {normalized}")
        if basename.endswith(".log"):
            findings.append(f"forbidden log file: {normalized}")

    return findings


def looks_allowed_placeholder(value: str) -> bool:
    upper = value.upper()
    lower = value.lower()
    return upper.startswith(ALLOWED_VALUE_PREFIXES) or any(fragment in lower for fragment in ALLOWED_VALUE_FRAGMENTS)


def is_allowed_secret_match(line: str, match: re.Match[str]) -> bool:
    value = match.group("value")
    if line[match.end("value") : match.end("value") + 1] == "(":
        return True
    return looks_allowed_placeholder(value)


def should_scan_text(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        return False
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return True


def find_content_findings(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for relative in paths:
        path = REPO_ROOT / relative
        if not should_scan_text(path):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in SECRET_ASSIGNMENT_RE.finditer(line):
                if is_allowed_secret_match(line, match):
                    continue
                findings.append(f"potential committed secret in {relative}:{line_number} for {match.group('name')}")
    return findings


def main() -> int:
    paths = tracked_files()
    findings = find_path_findings(paths) + find_content_findings(paths)
    if findings:
        print("Secret hygiene check failed:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Secret hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
