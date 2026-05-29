import json

import pytest

from scripts.testing import emulator_lab

pytestmark = [pytest.mark.simulated]


def test_emulator_lab_reports_synthetic_client_family_coverage():
    proof = emulator_lab.evaluate()

    assert proof["emulator_lab"] == "pass"
    assert proof["synthetic_profiles_cover_video_families"] == "pass"
    for family in ("roku", "fire_tv", "android_tv", "apple_tv", "ios", "ipados", "samsung_tv", "lg_tv", "console", "unknown"):
        assert family in proof["synthetic_video_profiles"]
    assert proof["unsupported_platforms_documented"] == "pass"
    assert proof["secret_logged"] == "no"


def test_emulator_lab_detects_vendor_commands(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("adb", "emulator", "avdmanager", "sdkmanager", "tizen", "sdb", "ares", "ares-setup-device"):
        path = bin_dir / command
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(emulator_lab, "avd_names", lambda: ["android-mobile-api35", "android-tv-api35", "google-tv-api35"])

    proof = emulator_lab.evaluate()

    assert proof["android_tools_present"] == "yes"
    assert proof["android_official_avds"] == "missing"
    assert proof["tizen_emulator"] == "available"
    assert proof["webos_emulator"] == "available"
    assert proof["android_avd_targets"]["android_mobile"] == "present"
    assert proof["android_avd_targets"]["android_tv"] == "present"
    assert proof["android_avd_targets"]["google_tv"] == "present"
    assert proof["android_mobile_avd"] == "present"
    assert proof["android_tv_avd"] == "present"
    assert proof["google_tv_avd"] == "present"


def test_emulator_lab_key_value_output_is_machine_parseable():
    proof = {
        "emulator_lab": "pass",
        "synthetic_video_profiles": ["roku", "android_tv"],
        "unsupported_by_host": {"apple_simulator": "requires macOS"},
    }

    lines = emulator_lab.flatten_key_values(proof)
    parsed = dict(line.split("=", 1) for line in lines)

    assert parsed["emulator_lab"] == "pass"
    assert json.loads(parsed["synthetic_video_profiles"]) == ["roku", "android_tv"]
    assert json.loads(parsed["unsupported_by_host"])["apple_simulator"] == "requires macOS"
