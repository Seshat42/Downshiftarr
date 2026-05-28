#!/usr/bin/env python3
"""Optional browser smoke check for the local Loki Plex web surface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from scripts.testing.loki_guard import DEFAULT_EXPECTED_MACHINE_IDENTIFIER, assert_loki_identity, fetch_identity, load_env_file

DEFAULT_ENV_FILE = Path("Downshiftarr.test.env")


def _env(name: str, values: dict[str, str], default: str = "") -> str:
    return os.environ.get(name) or values.get(name) or default


def run_browser_smoke(env_file: Path = DEFAULT_ENV_FILE) -> dict[str, Any]:
    env_values = load_env_file(env_file)
    base_url = _env("DOWNSHIFTARR_LOKI_PLEX_URL", env_values, "http://127.0.0.1:32400")
    token = _env("DOWNSHIFTARR_LOKI_PLEX_TOKEN", env_values)
    expected_machine_id = _env("DOWNSHIFTARR_LOKI_EXPECTED_MACHINE_ID", env_values, DEFAULT_EXPECTED_MACHINE_IDENTIFIER)
    enabled = _env("DOWNSHIFTARR_LOKI_BROWSER", env_values, "0") == "1"
    headless = _env("DOWNSHIFTARR_LOKI_BROWSER_HEADLESS", env_values, "1") != "0"

    identity = assert_loki_identity(fetch_identity(base_url, token=token or None), base_url, expected_machine_id or None)
    result: dict[str, Any] = {
        "identity": {"machine_identifier": identity.machine_identifier, "version": identity.version, "claimed": identity.claimed},
        "base_url": base_url,
        "status": "skipped",
        "reason": "DOWNSHIFTARR_LOKI_BROWSER is not 1",
    }
    if not enabled:
        return result

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["reason"] = "playwright is not installed in this Python environment"
        return result

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(f"{base_url.rstrip('/')}/identity", wait_until="domcontentloaded")
        body = page.locator("body").inner_text(timeout=5000)
        browser.close()

    if identity.machine_identifier not in body:
        raise RuntimeError("Loki Plex identity page did not include the expected machineIdentifier")

    result["status"] = "passed"
    result.pop("reason", None)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    args = parser.parse_args()

    print(json.dumps(run_browser_smoke(args.env_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
