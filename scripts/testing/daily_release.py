#!/usr/bin/env python3
"""Decide whether the nightly GitHub release workflow should publish today."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    created_at: str


@dataclass(frozen=True)
class ReleaseDecision:
    tag: str
    should_release: bool
    reason: str
    previous_release_tag: str | None
    commits_since_previous: int


def build_daily_tag(release_date: date) -> str:
    return f"daily-{release_date:%Y-%m-%d}"


def latest_prior_release(releases: list[ReleaseInfo], current_tag: str) -> ReleaseInfo | None:
    candidates = [release for release in releases if release.tag_name != current_tag]
    if not candidates:
        return None
    return sorted(candidates, key=lambda release: release.created_at, reverse=True)[0]


def decide_release(
    *,
    tag: str,
    tag_exists: bool,
    release_exists: bool,
    previous_release_tag: str | None,
    commits_since_previous: int,
) -> ReleaseDecision:
    if tag_exists or release_exists:
        return ReleaseDecision(tag, False, "daily tag or release already exists", previous_release_tag, commits_since_previous)
    if previous_release_tag is None:
        return ReleaseDecision(tag, True, "first daily release", previous_release_tag, commits_since_previous)
    if commits_since_previous <= 0:
        return ReleaseDecision(tag, False, "no commits since previous release", previous_release_tag, commits_since_previous)
    return ReleaseDecision(tag, True, "main changed since previous release", previous_release_tag, commits_since_previous)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def command_succeeds(command: list[str]) -> bool:
    return run(command, check=False).returncode == 0


def list_releases(repo: str) -> list[ReleaseInfo]:
    completed = run(
        [
            "gh",
            "release",
            "list",
            "--repo",
            repo,
            "--limit",
            "100",
            "--json",
            "tagName,createdAt",
            "--jq",
            ".[] | [.tagName, .createdAt] | @tsv",
        ]
    )
    releases: list[ReleaseInfo] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        tag_name, created_at = line.split("\t", 1)
        releases.append(ReleaseInfo(tag_name=tag_name, created_at=created_at))
    return releases


def ensure_tag(tag: str) -> None:
    if command_succeeds(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"]):
        return
    run(["git", "fetch", "origin", f"refs/tags/{tag}:refs/tags/{tag}"], check=False)


def count_commits_since(previous_tag: str | None, target_sha: str) -> int:
    if previous_tag is None:
        return int(run(["git", "rev-list", "--count", target_sha]).stdout.strip())
    ensure_tag(previous_tag)
    if not command_succeeds(["git", "rev-parse", "-q", "--verify", f"refs/tags/{previous_tag}"]):
        return int(run(["git", "rev-list", "--count", target_sha]).stdout.strip())
    return int(run(["git", "rev-list", "--count", f"{previous_tag}..{target_sha}"]).stdout.strip())


def today_new_york() -> date:
    return datetime.now(NEW_YORK).date()


def tag_exists_anywhere(tag: str) -> bool:
    return command_succeeds(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"]) or command_succeeds(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"]
    )


def release_exists(repo: str, tag: str) -> bool:
    return command_succeeds(["gh", "release", "view", tag, "--repo", repo])


def write_github_output(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def write_release_notes(path: Path, decision: ReleaseDecision, target_sha: str) -> None:
    previous = decision.previous_release_tag or "none"
    path.write_text(
        "\n".join(
            [
                f"# Downshiftarr {decision.tag}",
                "",
                f"- Target commit: `{target_sha}`",
                f"- Previous release tag: `{previous}`",
                f"- Commits since previous release: `{decision.commits_since_previous}`",
                "- GitHub Actions used no Plex, Tautulli, Loki, or local test secrets.",
                "- Release assets are limited to source distribution, wheel, checksums, and GitHub provenance attestations.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def decide_for_repository(repo: str, target_sha: str, release_date: date) -> ReleaseDecision:
    run(["git", "fetch", "--prune", "--tags", "origin"])
    tag = build_daily_tag(release_date)
    releases = list_releases(repo)
    previous = latest_prior_release(releases, tag)
    previous_tag = previous.tag_name if previous else None
    commits = count_commits_since(previous_tag, target_sha)
    return decide_release(
        tag=tag,
        tag_exists=tag_exists_anywhere(tag),
        release_exists=release_exists(repo, tag),
        previous_release_tag=previous_tag,
        commits_since_previous=commits,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Seshat42/Downshiftarr"))
    parser.add_argument("--target-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--release-date")
    parser.add_argument("--notes-file", default="release-notes.md")
    args = parser.parse_args(argv)

    target_sha = args.target_sha or run(["git", "rev-parse", "HEAD"]).stdout.strip()
    release_date = date.fromisoformat(args.release_date) if args.release_date else today_new_york()
    decision = decide_for_repository(args.repo, target_sha, release_date)

    write_release_notes(Path(args.notes_file), decision, target_sha)
    write_github_output(
        os.environ.get("GITHUB_OUTPUT"),
        {
            "tag": decision.tag,
            "should_release": "true" if decision.should_release else "false",
            "reason": decision.reason,
            "previous_tag": decision.previous_release_tag or "",
            "commit_count": str(decision.commits_since_previous),
            "target_sha": target_sha,
        },
    )
    print(f"{decision.tag}: {decision.reason}; should_release={decision.should_release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
