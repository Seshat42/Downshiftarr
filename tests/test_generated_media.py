import json
import shutil
import subprocess

import pytest

from scripts.testing.generate_media import MEDIA_SPECS, generate_all

pytestmark = [pytest.mark.media]


def test_generated_media_manifest_and_probe_match_specs(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for generated media tests")

    manifest = generate_all(tmp_path, duration=0.2)

    assert {entry["name"] for entry in manifest["media"]} == {spec.name for spec in MEDIA_SPECS}
    manifest_path = tmp_path / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest

    by_name = {entry["name"]: entry for entry in manifest["media"]}
    for spec in MEDIA_SPECS:
        entry = by_name[spec.name]
        path = tmp_path / entry["relative_path"]
        assert path.exists()
        if spec.expected_height is None:
            continue

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,color_transfer",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(probe.stdout)
        stream = data["streams"][0]
        assert stream["height"] == spec.expected_height
        assert stream["width"] == spec.expected_width
        if spec.dynamic_range == "HDR10":
            assert stream.get("color_transfer") == "smpte2084"
