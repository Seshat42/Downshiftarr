#!/usr/bin/env python3
"""Inspect release artifacts before they are attached to a GitHub release."""

from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.testing.verify_secret_hygiene import SECRET_ASSIGNMENT_RE, is_allowed_secret_match  # noqa: E402

ALLOWED_DIST_SUFFIXES = (".tar.gz", ".whl")
CHECKSUM_FILE = "SHA256SUMS.txt"
FORBIDDEN_ARCHIVE_SEGMENTS = {
    ".venv",
    "__pycache__",
    "artifacts",
    "codex-security-scans",
    "htmlcov",
    "local-tautulli",
    "playwright-report",
    "plex-test-media",
    "security-scans",
    "test-results",
}
FORBIDDEN_ARCHIVE_BASENAMES = {".env", "Downshiftarr.env", "Downshiftarr.test.env"}
FORBIDDEN_ARCHIVE_SUFFIXES = {
    ".avi",
    ".db",
    ".gif",
    ".jpeg",
    ".jpg",
    ".log",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".pyc",
    ".pyo",
    ".sarif",
    ".sqlite",
    ".sqlite3",
    ".webp",
}


def dist_assets(dist_dir: Path) -> list[Path]:
    return sorted(path for path in dist_dir.iterdir() if path.is_file() and path.name not in {CHECKSUM_FILE, ".gitignore"})


def parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    if not path.exists():
        return checksums
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            checksums[parts[1].lstrip("*")] = parts[0]
    return checksums


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def forbidden_archive_path(name: str) -> bool:
    parsed = Path(name)
    parts = set(parsed.parts)
    return (
        parsed.name in FORBIDDEN_ARCHIVE_BASENAMES
        or bool(parts & FORBIDDEN_ARCHIVE_SEGMENTS)
        or parsed.suffix.lower() in FORBIDDEN_ARCHIVE_SUFFIXES
        or "screenshot" in name.lower()
    )


def text_secret_findings(artifact: str, member: str, data: bytes) -> list[str]:
    if len(data) > 2_000_000:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []

    findings = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for match in SECRET_ASSIGNMENT_RE.finditer(line):
            if is_allowed_secret_match(line, match):
                continue
            findings.append(f"potential secret in {artifact}:{member}:{line_number} for {match.group('name')}")
    return findings


def inspect_wheel(path: Path) -> list[str]:
    findings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if forbidden_archive_path(name):
                findings.append(f"forbidden path in {path.name}: {name}")
            if name.endswith("/"):
                continue
            findings.extend(text_secret_findings(path.name, name, archive.read(name)))
    return findings


def inspect_sdist(path: Path) -> list[str]:
    findings: list[str] = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if forbidden_archive_path(member.name):
                findings.append(f"forbidden path in {path.name}: {member.name}")
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            findings.extend(text_secret_findings(path.name, member.name, extracted.read()))
    return findings


def validate_checksums(dist_dir: Path, assets: list[Path]) -> list[str]:
    checksums = parse_checksums(dist_dir / CHECKSUM_FILE)
    findings: list[str] = []
    for asset in assets:
        expected = checksums.get(asset.name)
        if expected is None:
            findings.append(f"missing checksum entry for {asset.name}")
            continue
        actual = sha256(asset)
        if expected.lower() != actual.lower():
            findings.append(f"checksum mismatch for {asset.name}")
    return findings


def find_artifact_findings(dist_dir: Path) -> list[str]:
    findings: list[str] = []
    if not dist_dir.exists():
        return [f"dist directory does not exist: {dist_dir}"]

    assets = dist_assets(dist_dir)
    if not assets:
        findings.append(f"no release assets found in {dist_dir}")

    for asset in assets:
        if not asset.name.endswith(ALLOWED_DIST_SUFFIXES):
            findings.append(f"unexpected release asset: {asset.name}")
            continue
        if asset.suffix == ".whl":
            findings.extend(inspect_wheel(asset))
        elif asset.name.endswith(".tar.gz"):
            findings.extend(inspect_sdist(asset))

    findings.extend(validate_checksums(dist_dir, assets))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist_dir", nargs="?", default="dist")
    args = parser.parse_args(argv)

    findings = find_artifact_findings(Path(args.dist_dir))
    if findings:
        print("Release artifact verification failed:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Release artifact verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
