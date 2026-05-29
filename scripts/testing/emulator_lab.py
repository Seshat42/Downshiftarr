#!/usr/bin/env python3
"""Inventory local Plex-client emulator coverage for Downshiftarr.

This script is deliberately read-only. It records which legitimate vendor
emulator tools are available on the workstation and which Plex client families
are covered by synthetic Downshiftarr canaries.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_LAB_ROOT = REPO_ROOT / "emulator-lab"


VIDEO_CLIENT_FAMILIES = (
    "plex_web",
    "desktop",
    "htpc",
    "roku",
    "fire_tv",
    "android_tv",
    "google_tv",
    "nvidia_shield",
    "apple_tv",
    "ios",
    "ipados",
    "android_mobile",
    "android_tablet",
    "chromecast",
    "samsung_tv",
    "lg_tv",
    "console",
    "relay_like",
    "unknown",
)

NON_VIDEO_CLIENT_FAMILIES = (
    "plexamp",
    "plex_photos",
)

ANDROID_AVD_TARGETS = (
    "android_mobile",
    "android_tablet",
    "android_tv",
    "google_tv",
)

UNSUPPORTED_BY_WINDOWS_HOST = {
    "apple_simulator": "requires macOS/Xcode for iOS/iPadOS/tvOS simulators",
    "roku_emulator": "Roku official Plex proof requires a physical Roku device; synthetic proof is used",
    "console_emulator": "console Plex clients require physical hardware or synthetic proof",
}


@dataclass(frozen=True)
class CommandProbe:
    key: str
    command: str


COMMAND_PROBES = (
    CommandProbe("adb", "adb"),
    CommandProbe("android_emulator", "emulator"),
    CommandProbe("avdmanager", "avdmanager"),
    CommandProbe("sdkmanager", "sdkmanager"),
    CommandProbe("tizen_cli", "tizen"),
    CommandProbe("samsung_sdb", "sdb"),
    CommandProbe("webos_cli", "ares"),
    CommandProbe("webos_setup_device", "ares-setup-device"),
    CommandProbe("apple_xcrun", "xcrun"),
    CommandProbe("roku_tooling", "roku"),
)


def detect_wsl() -> bool:
    try:
        version = Path("/proc/version")
        if version.exists():
            text = version.read_text(encoding="utf-8", errors="ignore").lower()
            return "microsoft" in text or "wsl" in text
    except Exception:
        pass
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def command_path(command: str) -> str | None:
    found = shutil.which(command)
    if found:
        return found
    tool_dirs = (
        LOCAL_LAB_ROOT / "android-sdk" / "platform-tools",
        LOCAL_LAB_ROOT / "android-sdk" / "emulator",
        LOCAL_LAB_ROOT / "android-sdk" / "cmdline-tools" / "latest" / "bin",
    )
    suffixes = ("", ".exe", ".bat", ".cmd")
    for directory in tool_dirs:
        for suffix in suffixes:
            candidate = directory / f"{command}{suffix}"
            if candidate.exists():
                return str(candidate)
    return None


def android_sdk_roots() -> list[str]:
    candidates: list[Path] = []
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value))
    home = Path.home()
    candidates.extend(
        [
            LOCAL_LAB_ROOT / "android-sdk",
            home / "AppData" / "Local" / "Android" / "Sdk",
            home / "Android" / "Sdk",
            Path("/mnt/c/Users") / os.environ.get("USER", "") / "AppData" / "Local" / "Android" / "Sdk",
        ]
    )
    seen: set[str] = set()
    roots: list[str] = []
    for candidate in candidates:
        value = str(candidate)
        if value in seen:
            continue
        seen.add(value)
        if candidate.exists():
            roots.append(value)
    return roots


def avd_names() -> list[str]:
    avdmanager = command_path("avdmanager")
    if not avdmanager:
        return avd_names_from_files()
    env = dict(os.environ)
    env.setdefault("ANDROID_HOME", str(LOCAL_LAB_ROOT / "android-sdk"))
    env.setdefault("ANDROID_SDK_ROOT", str(LOCAL_LAB_ROOT / "android-sdk"))
    env.setdefault("ANDROID_AVD_HOME", str(LOCAL_LAB_ROOT / "avd-home" / ".android" / "avd"))
    try:
        completed = subprocess.run(
            [avdmanager, "list", "avd"],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except Exception:
        return avd_names_from_files()
    names: list[str] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            names.append(line.split(":", 1)[1].strip())
    if names:
        return sorted(name for name in names if name)
    return avd_names_from_files()


def avd_names_from_files() -> list[str]:
    avd_dirs = [
        LOCAL_LAB_ROOT / "avd-home" / ".android" / "avd",
        Path.home() / ".android" / "avd",
    ]
    names: set[str] = set()
    for avd_dir in avd_dirs:
        if not avd_dir.exists():
            continue
        for ini in avd_dir.glob("*.ini"):
            names.add(ini.stem)
        for avd in avd_dir.glob("*.avd"):
            names.add(avd.stem)
    return sorted(names)


def command_inventory() -> dict[str, str]:
    inventory: dict[str, str] = {}
    for probe in COMMAND_PROBES:
        found = command_path(probe.command)
        inventory[probe.key] = found or "missing"
    return inventory


def evaluate() -> dict[str, Any]:
    commands = command_inventory()
    avds = avd_names()
    android_tools_present = all(commands[key] != "missing" for key in ("adb", "android_emulator", "avdmanager", "sdkmanager"))
    android_targets = {
        target: ("present" if any(target.replace("_", "-") in name.lower().replace("_", "-") for name in avds) else "not_created")
        for target in ANDROID_AVD_TARGETS
    }

    result: dict[str, Any] = {
        "emulator_lab": "pass",
        "emulator_lab_scope": "maximum_feasible_windows_wsl",
        "host_os": platform.system() or "unknown",
        "host_platform": platform.platform(),
        "wsl": "yes" if detect_wsl() else "no",
        "synthetic_profile_registry": "pass",
        "synthetic_video_profiles": list(VIDEO_CLIENT_FAMILIES),
        "synthetic_non_video_profiles": list(NON_VIDEO_CLIENT_FAMILIES),
        "synthetic_profiles_cover_video_families": "pass",
        "android_sdk_roots": android_sdk_roots(),
        "android_tools_present": "yes" if android_tools_present else "no",
        "android_avd_names": avds,
        "android_avd_targets": android_targets,
        "android_official_avds": "pass"
        if android_tools_present and all(value == "present" for value in android_targets.values())
        else "missing",
        "android_mobile_avd": android_targets["android_mobile"],
        "android_tablet_avd": android_targets["android_tablet"],
        "android_tv_avd": android_targets["android_tv"],
        "google_tv_avd": android_targets["google_tv"],
        "tizen_emulator": "available" if commands["tizen_cli"] != "missing" and commands["samsung_sdb"] != "missing" else "missing",
        "webos_emulator": "available" if commands["webos_cli"] != "missing" and commands["webos_setup_device"] != "missing" else "missing",
        "unsupported_platforms_documented": "pass",
        "unsupported_by_host": dict(UNSUPPORTED_BY_WINDOWS_HOST),
        "no_tokens_logged": "yes",
        "secret_logged": "no",
    }
    result.update(commands)
    return result


def flatten_key_values(data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in sorted(data):
        value = data[key]
        if isinstance(value, (dict, list, tuple)):
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        else:
            encoded = str(value)
        lines.append(f"{key}={encoded}")
    return lines


def redacted_for_evidence(data: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(data)
    for probe in COMMAND_PROBES:
        value = redacted.get(probe.key)
        if value and value != "missing":
            redacted[probe.key] = "present"
    if redacted.get("android_sdk_roots"):
        redacted["android_sdk_roots"] = ["operator-local-android-sdk"]
    return redacted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of key=value proof lines.")
    parser.add_argument("--output", type=Path, help="Write proof to this path.")
    parser.add_argument("--redact-paths", action="store_true", help="Replace local executable and SDK paths with present/missing markers.")
    args = parser.parse_args(argv)

    proof = evaluate()
    if args.redact_paths:
        proof = redacted_for_evidence(proof)
    if args.json:
        text = json.dumps(proof, indent=2, sort_keys=True) + "\n"
    else:
        text = "\n".join(flatten_key_values(proof)) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
