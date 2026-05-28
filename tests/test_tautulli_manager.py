import json
from pathlib import Path

import pytest

from scripts.testing import tautulli_manager

pytestmark = [pytest.mark.unit]


def test_tautulli_manager_builds_namespaced_loopback_docker_run(tmp_path):
    command = tautulli_manager.build_docker_run_command(host_port=18181, config_dir=tmp_path / "config")

    assert command[:4] == ["docker", "run", "-d", "--name"]
    assert tautulli_manager.CONTAINER_NAME in command
    assert "-p" in command
    assert "127.0.0.1:18181:8181" in command
    assert tautulli_manager.DEFAULT_IMAGE in command
    assert "--restart" not in command
    assert "--add-host" in command
    assert "host.docker.internal:host-gateway" in command
    assert any(arg == "downshiftarr.project=Downshiftarr" for arg in command)
    assert any(arg == "downshiftarr.managed=true" for arg in command)
    assert str((tmp_path / "config").resolve()) + ":/config" in command


def test_tautulli_manager_rejects_unmanaged_existing_container():
    inspect = {
        "Name": f"/{tautulli_manager.CONTAINER_NAME}",
        "Config": {"Labels": {"some.other": "label"}},
        "State": {"Running": True},
    }

    with pytest.raises(RuntimeError, match="not managed by Downshiftarr"):
        tautulli_manager.assert_downshiftarr_managed(inspect)


def test_tautulli_manager_accepts_only_downshiftarr_labeled_container():
    inspect = {
        "Name": f"/{tautulli_manager.CONTAINER_NAME}",
        "Config": {"Labels": tautulli_manager.REQUIRED_LABELS},
        "State": {"Running": False},
    }

    assert tautulli_manager.assert_downshiftarr_managed(inspect) is None


def test_tautulli_manager_selects_first_available_port(monkeypatch):
    occupied = {18181, 18182}
    monkeypatch.setattr(tautulli_manager, "port_available", lambda port, host="127.0.0.1": port not in occupied)

    assert tautulli_manager.choose_host_port() == 18183


def test_tautulli_manager_updates_env_without_printing_secrets(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("PLEX_TOKEN=secret-token\nTAUTULLI_URL=http://old:8181\n", encoding="utf-8")

    tautulli_manager.upsert_env_values(env_path, {"TAUTULLI_URL": "http://127.0.0.1:18181", "TAUTULLI_APIKEY": "api-secret"})

    text = env_path.read_text(encoding="utf-8")
    assert "TAUTULLI_URL=http://127.0.0.1:18181" in text
    assert "TAUTULLI_APIKEY=api-secret" in text
    assert "PLEX_TOKEN=secret-token" in text


def test_tautulli_manager_writes_test_and_runtime_aliases_to_test_env(tmp_path):
    env_path = tmp_path / "Downshiftarr.test.env"

    tautulli_manager.upsert_env_values(
        env_path,
        tautulli_manager.tautulli_env_updates("http://127.0.0.1:18181", "api-secret"),
    )

    text = env_path.read_text(encoding="utf-8")
    assert "DOWNSHIFTARR_TAUTULLI_URL=http://127.0.0.1:18181" in text
    assert "DOWNSHIFTARR_TAUTULLI_APIKEY=api-secret" in text
    assert "TAUTULLI_URL=http://127.0.0.1:18181" in text
    assert "TAUTULLI_APIKEY=api-secret" in text


def test_tautulli_manager_defaults_to_test_env_not_runtime_env():
    assert tautulli_manager.DEFAULT_ENV_FILE == Path("Downshiftarr.test.env")
    assert tautulli_manager.DEFAULT_IMAGE.startswith("linuxserver/")
    assert "ghcr.io" not in tautulli_manager.DEFAULT_IMAGE


def test_tautulli_manager_parses_docker_inspect_payload():
    payload = json.dumps([{"Name": f"/{tautulli_manager.CONTAINER_NAME}", "Config": {"Labels": tautulli_manager.REQUIRED_LABELS}}])

    assert tautulli_manager.parse_docker_inspect(payload)["Name"] == f"/{tautulli_manager.CONTAINER_NAME}"


def test_tautulli_manager_down_commands_are_label_guarded(monkeypatch):
    inspected = {
        "Name": f"/{tautulli_manager.CONTAINER_NAME}",
        "Config": {"Labels": tautulli_manager.REQUIRED_LABELS},
        "State": {"Running": True},
    }
    commands = []
    monkeypatch.setattr(tautulli_manager, "inspect_container", lambda: inspected)
    monkeypatch.setattr(tautulli_manager, "run_command", lambda command, capture=False: commands.append(command))

    tautulli_manager.stop_container()
    tautulli_manager.remove_container()

    assert commands == [["docker", "stop", tautulli_manager.CONTAINER_NAME], ["docker", "rm", tautulli_manager.CONTAINER_NAME]]


def test_loki_probe_command_is_temporary_and_namespaced():
    command = tautulli_manager.build_loki_probe_command("http://host.docker.internal:32400/identity")

    assert command[:3] == ["docker", "run", "--rm"]
    assert "--name" in command
    assert "downshiftarr-loki-probe" in command
    assert "--add-host" in command
    assert "host.docker.internal:host-gateway" in command
    assert any(arg == "downshiftarr.managed=true" for arg in command)
    assert "curlimages/curl:latest" in command
    assert "http://host.docker.internal:32400/identity" in command


def test_configure_config_ini_connects_to_loki_and_disables_remote_update_checks(tmp_path):
    config_ini = tmp_path / "config.ini"
    config_ini.write_text(
        "[General]\napi_key = generated-key\nfirst_run_complete = 0\ncheck_github = 1\ncheck_github_on_startup = 1\n"
        'pms_ip = 127.0.0.1\npms_port = 32400\npms_token = ""\npms_identifier = ""\npms_url = ""\n',
        encoding="utf-8",
    )

    api_key = tautulli_manager.configure_config_ini(
        config_ini,
        pms_host="host.docker.internal",
        pms_port=32400,
        pms_token="plex-token",
        pms_identifier="loki-id",
        pms_version="1.2.3",
        pms_name="Loki",
    )
    text = config_ini.read_text(encoding="utf-8")

    assert api_key == "generated-key"
    assert "first_run_complete = 1" in text
    assert "check_github = 0" in text
    assert "check_github_on_startup = 0" in text
    assert "[PMS]" in text
    assert "pms_ip = host.docker.internal" in text
    assert "pms_token = plex-token" in text
    assert "pms_identifier = loki-id" in text
    assert "pms_url = http://host.docker.internal:32400" in text
