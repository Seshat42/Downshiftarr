import os

import pytest

from scripts.testing import local_config

pytestmark = [pytest.mark.unit]


def write_env(path, values):
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")


def test_local_config_precedence_shell_then_test_env_then_runtime_env(tmp_path, monkeypatch):
    runtime_env = tmp_path / ".env"
    test_env = tmp_path / "Downshiftarr.test.env"
    write_env(
        runtime_env,
        {
            "PLEX_URL": "http://runtime-plex:32400",
            "PLEX_TOKEN": "runtime-token",
            "TAUTULLI_URL": "http://runtime-tautulli:18181",
            "TAUTULLI_APIKEY": "runtime-api-key",
        },
    )
    write_env(
        test_env,
        {
            "DOWNSHIFTARR_LOKI_PLEX_URL": "http://test-plex:32400",
            "DOWNSHIFTARR_TAUTULLI_URL": "http://test-tautulli:18181",
        },
    )
    monkeypatch.setenv("DOWNSHIFTARR_LOKI_PLEX_TOKEN", "shell-token")

    config = local_config.load_local_test_config(test_env_file=test_env, runtime_env_file=runtime_env, environ=os.environ)

    assert config["DOWNSHIFTARR_LOKI_PLEX_URL"] == "http://test-plex:32400"
    assert config["DOWNSHIFTARR_LOKI_PLEX_TOKEN"] == "shell-token"
    assert config["DOWNSHIFTARR_TAUTULLI_URL"] == "http://test-tautulli:18181"
    assert config["DOWNSHIFTARR_TAUTULLI_APIKEY"] == "runtime-api-key"


def test_local_config_maps_runtime_env_names_to_loki_aliases(tmp_path, monkeypatch):
    monkeypatch.delenv("DOWNSHIFTARR_LOKI_PLEX_URL", raising=False)
    runtime_env = tmp_path / ".env"
    write_env(runtime_env, {"PLEX_URL": "http://127.0.0.1:32400", "PLEX_TOKEN": "secret", "TAUTULLI_URL": "http://127.0.0.1:18181"})

    config = local_config.load_local_test_config(test_env_file=tmp_path / "missing.env", runtime_env_file=runtime_env, environ={})

    assert config["DOWNSHIFTARR_LOKI_PLEX_URL"] == "http://127.0.0.1:32400"
    assert config["DOWNSHIFTARR_LOKI_PLEX_TOKEN"] == "secret"
    assert config["DOWNSHIFTARR_TAUTULLI_URL"] == "http://127.0.0.1:18181"


def test_secret_redaction_masks_config_values():
    text = "PLEX_TOKEN=secret-token TAUTULLI_APIKEY=api-key DOWNSHIFTARR_LOKI_PLEX_TOKEN=secret-token"
    redacted = local_config.redact_secrets(text, {"PLEX_TOKEN": "secret-token", "TAUTULLI_APIKEY": "api-key"})

    assert "secret-token" not in redacted
    assert "api-key" not in redacted
    assert redacted.count("<redacted>") == 3
