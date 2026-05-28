#!/usr/bin/env python3
"""Local-only test configuration loading helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

DEFAULT_TEST_ENV_FILE = Path("Downshiftarr.test.env")
DEFAULT_RUNTIME_ENV_FILE = Path(".env")

RUNTIME_TO_TEST_ALIASES = {
    "PLEX_URL": "DOWNSHIFTARR_LOKI_PLEX_URL",
    "PLEX_TOKEN": "DOWNSHIFTARR_LOKI_PLEX_TOKEN",
    "TAUTULLI_URL": "DOWNSHIFTARR_TAUTULLI_URL",
    "TAUTULLI_APIKEY": "DOWNSHIFTARR_TAUTULLI_APIKEY",
}

SECRET_KEYS = {
    "PLEX_TOKEN",
    "PLEX_USER_TOKEN",
    "TAUTULLI_APIKEY",
    "DOWNSHIFTARR_LOKI_PLEX_TOKEN",
    "DOWNSHIFTARR_TAUTULLI_APIKEY",
}


def load_env_file(path: str | os.PathLike[str] | Path) -> dict[str, str]:
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    with env_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def with_test_aliases(values: Mapping[str, str]) -> dict[str, str]:
    aliased = dict(values)
    for source_key, target_key in RUNTIME_TO_TEST_ALIASES.items():
        if source_key in values and target_key not in aliased:
            aliased[target_key] = values[source_key]
    return aliased


def load_local_test_config(
    test_env_file: str | os.PathLike[str] | Path = DEFAULT_TEST_ENV_FILE,
    runtime_env_file: str | os.PathLike[str] | Path = DEFAULT_RUNTIME_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    runtime_values = with_test_aliases(load_env_file(runtime_env_file))
    test_values = with_test_aliases(load_env_file(test_env_file))
    shell_values = with_test_aliases(environ if environ is not None else os.environ)
    return {**runtime_values, **test_values, **shell_values}


def redact_secrets(text: str, values: Mapping[str, str]) -> str:
    redacted = text
    for key, value in values.items():
        if value and (key in SECRET_KEYS or "TOKEN" in key or "APIKEY" in key or "API_KEY" in key):
            redacted = redacted.replace(value, "<redacted>")
    return redacted
