#!/usr/bin/env python3
"""Run opt-in generated-media checks against the local Loki Plex server."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from scripts.testing.generate_media import DEFAULT_OUTPUT_DIR, generate_all
from scripts.testing.loki_guard import assert_loki_identity, fetch_identity, load_env_file

DEFAULT_ENV_FILE = Path("Downshiftarr.test.env")
DEFAULT_LIBRARY_NAME = "Downshiftarr Test Rig"


def _env(name: str, values: dict[str, str], default: str = "") -> str:
    return os.environ.get(name) or values.get(name) or default


def _plex_request(
    base_url: str, path: str, token: str, params: dict[str, str] | None = None, method: str = "GET"
) -> urllib.request.Request:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return urllib.request.Request(url, headers={"Accept": "application/json", "X-Plex-Token": token}, method=method)


def _plex_json(base_url: str, path: str, token: str, params: dict[str, str] | None = None, method: str = "GET") -> dict[str, Any]:
    with urllib.request.urlopen(_plex_request(base_url, path, token, params=params, method=method), timeout=10) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8") or "{}")


def find_library_section(base_url: str, token: str, library_name: str) -> str | None:
    data = _plex_json(base_url, "/library/sections", token)
    directories = (data.get("MediaContainer") or {}).get("Directory") or []
    if isinstance(directories, dict):
        directories = [directories]
    for directory in directories:
        if directory.get("title") == library_name:
            return str(directory.get("key"))
    return None


def create_movie_library(base_url: str, token: str, library_name: str, media_dir: Path) -> str | None:
    params = {
        "name": library_name,
        "type": "movie",
        "agent": "tv.plex.agents.movie",
        "scanner": "Plex Movie",
        "language": "en-US",
        "location": str(media_dir),
    }
    _plex_json(base_url, "/library/sections", token, params=params, method="POST")
    return find_library_section(base_url, token, library_name)


def refresh_library_section(base_url: str, token: str, section_id: str, media_dir: Path) -> None:
    _plex_json(base_url, f"/library/sections/{section_id}/refresh", token, params={"path": str(media_dir)})


def run_matrix(env_file: Path = DEFAULT_ENV_FILE, destructive: bool = False, create_library: bool = False) -> dict[str, Any]:
    env_values = load_env_file(env_file)
    base_url = _env("DOWNSHIFTARR_LOKI_PLEX_URL", env_values, "http://127.0.0.1:32400")
    token = _env("DOWNSHIFTARR_LOKI_PLEX_TOKEN", env_values)
    expected_machine_id = _env("DOWNSHIFTARR_LOKI_EXPECTED_MACHINE_ID", env_values)
    library_name = _env("DOWNSHIFTARR_LOKI_TEST_LIBRARY_NAME", env_values, DEFAULT_LIBRARY_NAME)
    media_dir = Path(_env("DOWNSHIFTARR_TEST_MEDIA_DIR", env_values, str(DEFAULT_OUTPUT_DIR))).resolve()
    allow_destructive = _env("DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE", env_values) == "1"

    identity = assert_loki_identity(fetch_identity(base_url, token=token or None), base_url, expected_machine_id or None)
    manifest = generate_all(media_dir)

    result: dict[str, Any] = {
        "identity": {"machine_identifier": identity.machine_identifier, "version": identity.version, "claimed": identity.claimed},
        "media_dir": str(media_dir),
        "generated_media": [entry["name"] for entry in manifest["media"]],
        "library_name": library_name,
        "library_section_id": None,
        "destructive": destructive,
    }

    if not destructive:
        result["status"] = "guard-and-media-only"
        return result

    if not allow_destructive:
        raise RuntimeError("Set DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1 before running destructive Loki tests")
    if not token:
        raise RuntimeError("DOWNSHIFTARR_LOKI_PLEX_TOKEN is required for destructive Loki library refresh tests")

    section_id = find_library_section(base_url, token, library_name)
    if section_id is None and create_library:
        section_id = create_movie_library(base_url, token, library_name, media_dir)
    if section_id is None:
        raise RuntimeError(f"Plex test library {library_name!r} was not found; create it on Loki or pass --create-library")

    refresh_library_section(base_url, token, section_id, media_dir)
    result["library_section_id"] = section_id
    result["status"] = "library-refresh-requested"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--destructive", action="store_true")
    parser.add_argument("--create-library", action="store_true")
    args = parser.parse_args()

    print(json.dumps(run_matrix(args.env_file, destructive=args.destructive, create_library=args.create_library), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
