#!/usr/bin/env python3
"""Manage the isolated local Tautulli container used by Downshiftarr tests."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from scripts.testing.local_config import load_local_test_config, redact_secrets
from scripts.testing.loki_guard import assert_loki_identity, fetch_identity

CONTAINER_NAME = "downshiftarr-tautulli"
DEFAULT_IMAGE = "linuxserver/tautulli:latest"
PROBE_IMAGE = "curlimages/curl:latest"
PROBE_CONTAINER_NAME = "downshiftarr-loki-probe"
DEFAULT_CONFIG_DIR = Path("artifacts/local-tautulli/config")
DEFAULT_ENV_FILE = Path("Downshiftarr.test.env")
DEFAULT_HOST = "127.0.0.1"
TAUTULLI_CONTAINER_PORT = 8181
HOST_PORTS = tuple(range(18181, 18191))
REQUIRED_LABELS = {
    "downshiftarr.project": "Downshiftarr",
    "downshiftarr.role": "tautulli",
    "downshiftarr.managed": "true",
}


def port_available(port: int, host: str = DEFAULT_HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def choose_host_port() -> int:
    for port in HOST_PORTS:
        if port_available(port):
            return port
    raise RuntimeError(f"No free Downshiftarr Tautulli port found in {HOST_PORTS[0]}-{HOST_PORTS[-1]}")


def build_docker_run_command(host_port: int, config_dir: Path = DEFAULT_CONFIG_DIR, image: str = DEFAULT_IMAGE) -> list[str]:
    config_mount = f"{config_dir.resolve()}:/config"
    labels = [item for key, value in REQUIRED_LABELS.items() for item in ("--label", f"{key}={value}")]
    return [
        "docker",
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        *labels,
        "--add-host",
        "host.docker.internal:host-gateway",
        "-p",
        f"{DEFAULT_HOST}:{host_port}:{TAUTULLI_CONTAINER_PORT}",
        "-v",
        config_mount,
        "-e",
        f"TZ={os.environ.get('TZ', 'America/New_York')}",
        image,
    ]


def build_loki_probe_command(url: str, image: str = PROBE_IMAGE) -> list[str]:
    labels = [item for key, value in REQUIRED_LABELS.items() for item in ("--label", f"{key}={value}")]
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        PROBE_CONTAINER_NAME,
        *labels,
        "--add-host",
        "host.docker.internal:host-gateway",
        image,
        "-fsS",
        "--max-time",
        "5",
        url,
    ]


def parse_docker_inspect(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unable to parse docker inspect output: {exc}") from exc
    if not data:
        return None
    if not isinstance(data, list) or not isinstance(data[0], dict):
        raise RuntimeError("Unexpected docker inspect output shape")
    return data[0]


def assert_downshiftarr_managed(inspect: dict[str, Any]) -> None:
    labels = (inspect.get("Config") or {}).get("Labels") or {}
    missing = {key: value for key, value in REQUIRED_LABELS.items() if labels.get(key) != value}
    if missing:
        raise RuntimeError(f"Container {CONTAINER_NAME!r} exists but is not managed by Downshiftarr; refusing to touch it")


def run_command(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=capture, text=True)


def inspect_container() -> dict[str, Any] | None:
    completed = subprocess.run(["docker", "inspect", CONTAINER_NAME], capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    return parse_docker_inspect(completed.stdout)


def stop_container() -> dict[str, Any]:
    inspected = inspect_container()
    if not inspected:
        return {"container": CONTAINER_NAME, "exists": False, "stopped": False}
    assert_downshiftarr_managed(inspected)
    if (inspected.get("State") or {}).get("Running"):
        run_command(["docker", "stop", CONTAINER_NAME], capture=True)
    return {"container": CONTAINER_NAME, "exists": True, "stopped": True}


def remove_container() -> dict[str, Any]:
    inspected = inspect_container()
    if not inspected:
        return {"container": CONTAINER_NAME, "exists": False, "removed": False}
    assert_downshiftarr_managed(inspected)
    run_command(["docker", "rm", CONTAINER_NAME], capture=True)
    return {"container": CONTAINER_NAME, "exists": True, "removed": True}


def upsert_env_values(env_path: Path, updates: dict[str, str]) -> None:
    existing: list[str] = []
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8").splitlines()

    seen = set()
    output: list[str] = []
    for line in existing:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)

    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")

    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def tautulli_env_updates(tautulli_url: str, api_key: str) -> dict[str, str]:
    return {
        "DOWNSHIFTARR_TAUTULLI_URL": tautulli_url,
        "DOWNSHIFTARR_TAUTULLI_APIKEY": api_key,
        "TAUTULLI_URL": tautulli_url,
        "TAUTULLI_APIKEY": api_key,
    }


def wait_for_file(path: Path, timeout_s: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(1)
    return False


def configure_config_ini(
    config_ini: Path,
    *,
    pms_host: str,
    pms_port: int,
    pms_token: str,
    pms_identifier: str,
    pms_version: str,
    pms_name: str = "Loki",
) -> str:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(config_ini, encoding="utf-8")
    if not parser.has_section("General"):
        parser.add_section("General")

    general = parser["General"]
    general["first_run_complete"] = "1"
    general["launch_browser"] = "0"
    general["launch_startup"] = "0"
    general["check_github"] = "0"
    general["check_github_on_startup"] = "0"
    general["pms_ip"] = pms_host
    general["pms_port"] = str(pms_port)
    general["pms_ssl"] = "0"
    general["pms_is_cloud"] = "0"
    general["pms_is_remote"] = "0"
    general["pms_url_manual"] = "1"
    general["pms_url"] = f"http://{pms_host}:{pms_port}"
    general["pms_url_override"] = f"http://{pms_host}:{pms_port}"
    general["pms_token"] = pms_token
    general["pms_identifier"] = pms_identifier
    general["pms_name"] = pms_name
    general["pms_version"] = pms_version
    general["http_username"] = "downshiftarr"
    general["http_password"] = ""
    general["http_hash_password"] = "0"
    general["http_hashed_password"] = "0"
    general["api_enabled"] = "1"

    api_key = general.get("api_key", "").strip()
    pms_keys = [key for key in general if key.startswith("pms_")]
    for key in pms_keys:
        general.pop(key, None)

    if not parser.has_section("PMS"):
        parser.add_section("PMS")
    pms = parser["PMS"]
    pms["pms_ip"] = pms_host
    pms["pms_port"] = str(pms_port)
    pms["pms_ssl"] = "0"
    pms["pms_is_cloud"] = "0"
    pms["pms_is_remote"] = "0"
    pms["pms_url_manual"] = "1"
    pms["pms_url"] = f"http://{pms_host}:{pms_port}"
    pms["pms_url_override"] = f"http://{pms_host}:{pms_port}"
    pms["pms_token"] = pms_token
    pms["pms_identifier"] = pms_identifier
    pms["pms_name"] = pms_name
    pms["pms_version"] = pms_version

    with config_ini.open("w", encoding="utf-8") as handle:
        parser.write(handle, space_around_delimiters=True)
    return api_key


def build_tautulli_url(host_port: int) -> str:
    return f"http://{DEFAULT_HOST}:{host_port}"


def wait_for_http(url: str, timeout_s: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(2)
    return False


def probe_docker_loki(base_url: str = "http://host.docker.internal:32400") -> bool:
    completed = subprocess.run(build_loki_probe_command(f"{base_url.rstrip('/')}/identity"), capture_output=True, text=True)
    return completed.returncode == 0


def ensure_container(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    env_path: Path = DEFAULT_ENV_FILE,
    image: str = DEFAULT_IMAGE,
    require_loki_probe: bool = True,
) -> dict[str, Any]:
    config = load_local_test_config(test_env_file=env_path)
    plex_url = config.get("DOWNSHIFTARR_LOKI_PLEX_URL") or "http://127.0.0.1:32400"
    plex_token = config.get("DOWNSHIFTARR_LOKI_PLEX_TOKEN") or None
    expected_machine_id = config.get("DOWNSHIFTARR_LOKI_EXPECTED_MACHINE_ID")
    identity = assert_loki_identity(fetch_identity(plex_url, token=plex_token), plex_url, expected_machine_id or None)

    if require_loki_probe and not probe_docker_loki():
        raise RuntimeError("Docker containers cannot reach Loki at http://host.docker.internal:32400/identity; refusing to start Tautulli")

    config_dir.mkdir(parents=True, exist_ok=True)
    inspected = inspect_container()
    if inspected:
        assert_downshiftarr_managed(inspected)
        running = bool((inspected.get("State") or {}).get("Running"))
        ports = ((inspected.get("NetworkSettings") or {}).get("Ports") or {}).get(f"{TAUTULLI_CONTAINER_PORT}/tcp") or []
        host_port = int(ports[0]["HostPort"]) if ports else choose_host_port()
        if not running:
            run_command(["docker", "start", CONTAINER_NAME], capture=True)
    else:
        host_port = choose_host_port()
        run_command(build_docker_run_command(host_port, config_dir=config_dir, image=image), capture=True)

    tautulli_url = build_tautulli_url(host_port)
    ready = wait_for_http(tautulli_url)
    config_ini = config_dir / "config.ini"
    if not wait_for_file(config_ini):
        raise RuntimeError(f"Tautulli config file was not created: {config_ini}")

    stop_container()
    api_key = configure_config_ini(
        config_ini,
        pms_host="host.docker.internal",
        pms_port=32400,
        pms_token=plex_token or "",
        pms_identifier=identity.machine_identifier,
        pms_version=identity.version,
    )
    upsert_env_values(env_path, tautulli_env_updates(tautulli_url, api_key))
    run_command(["docker", "start", CONTAINER_NAME], capture=True)
    ready = wait_for_http(tautulli_url)
    return {"container": CONTAINER_NAME, "tautulli_url": tautulli_url, "config_dir": str(config_dir), "ready": ready, "api_key": api_key}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["up", "status", "probe-loki", "down", "rm"])
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--skip-loki-probe", action="store_true", help="Start the sidecar even if the Docker-to-Loki probe is skipped.")
    args = parser.parse_args(argv)

    if args.command == "status":
        inspected = inspect_container()
        if inspected:
            assert_downshiftarr_managed(inspected)
            print(
                json.dumps(
                    {"container": CONTAINER_NAME, "exists": True, "running": bool((inspected.get("State") or {}).get("Running"))}, indent=2
                )
            )
        else:
            print(json.dumps({"container": CONTAINER_NAME, "exists": False}, indent=2))
        return 0

    if args.command == "down":
        print(json.dumps(stop_container(), indent=2))
        return 0

    if args.command == "rm":
        print(json.dumps(remove_container(), indent=2))
        return 0

    if args.command == "probe-loki":
        ok = probe_docker_loki()
        print(json.dumps({"docker_loki_reachable": ok, "url": "http://host.docker.internal:32400/identity"}, indent=2))
        return 0 if ok else 1

    result = ensure_container(args.config_dir, args.env_file, image=args.image, require_loki_probe=not args.skip_loki_probe)
    print(redact_secrets(json.dumps(result, indent=2), load_local_test_config(test_env_file=args.env_file)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
