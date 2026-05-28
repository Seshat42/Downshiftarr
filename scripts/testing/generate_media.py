#!/usr/bin/env python3
"""Generate deterministic local media fixtures for Downshiftarr testing."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = Path("artifacts/plex-test-media")


@dataclass(frozen=True)
class MediaSpec:
    name: str
    filename: str
    expected_width: int | None
    expected_height: int | None
    dynamic_range: str
    kind: str = "video"


MEDIA_SPECS: tuple[MediaSpec, ...] = (
    MediaSpec("480p-sdr", "downshiftarr-480p-sdr.mp4", 854, 480, "SDR"),
    MediaSpec("720p-sdr", "downshiftarr-720p-sdr.mp4", 1280, 720, "SDR"),
    MediaSpec("1080p-sdr", "downshiftarr-1080p-sdr.mp4", 1920, 1080, "SDR"),
    MediaSpec("2160p-sdr", "downshiftarr-2160p-sdr.mp4", 3840, 2160, "SDR"),
    MediaSpec("2160p-hdr10-like", "downshiftarr-2160p-hdr10-like.mp4", 3840, 2160, "HDR10"),
    MediaSpec("audio-only-invalid", "downshiftarr-audio-only-invalid.m4a", None, None, "UNKNOWN", kind="audio"),
    MediaSpec("malformed-unknown-metadata", "downshiftarr-malformed-unknown-metadata.json", None, None, "UNKNOWN", kind="metadata"),
)


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg was not found on PATH")
    return exe


def _ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError("ffprobe was not found on PATH")
    return exe


def _video_command(spec: MediaSpec, output_path: Path, duration: float) -> list[str]:
    assert spec.expected_width is not None
    assert spec.expected_height is not None
    command = [
        _ffmpeg(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={spec.expected_width}x{spec.expected_height}:rate=12:duration={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=1000:duration={duration}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "35",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
    ]
    if spec.dynamic_range == "HDR10":
        command.extend(
            [
                "-bsf:v",
                "h264_metadata=colour_primaries=9:transfer_characteristics=16:matrix_coefficients=9",
            ]
        )
    command.append(str(output_path))
    return command


def _audio_command(output_path: Path, duration: float) -> list[str]:
    return [
        _ffmpeg(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-c:a",
        "aac",
        str(output_path),
    ]


def _probe_video(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            _ffprobe(),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,color_transfer,color_space,color_primaries",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    return dict(streams[0]) if streams else {}


def _manifest_entry(spec: MediaSpec, output_dir: Path) -> dict[str, Any]:
    path = output_dir / spec.filename
    entry = asdict(spec)
    entry["relative_path"] = spec.filename
    entry["bytes"] = path.stat().st_size if path.exists() else 0
    if spec.kind == "video":
        entry["ffprobe"] = _probe_video(path)
    return entry


def generate_all(output_dir: Path = DEFAULT_OUTPUT_DIR, duration: float = 1.0) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec in MEDIA_SPECS:
        output_path = output_dir / spec.filename
        if spec.kind == "video":
            _run(_video_command(spec, output_path, duration))
        elif spec.kind == "audio":
            _run(_audio_command(output_path, duration))
        elif spec.kind == "metadata":
            output_path.write_text(
                json.dumps({"MediaContainer": {"Metadata": [{"title": "malformed unknown fixture", "Media": []}]}}, indent=2),
                encoding="utf-8",
            )
        else:
            raise RuntimeError(f"Unknown media fixture kind: {spec.kind}")

    manifest = {"schema_version": 1, "duration_seconds": duration, "media": [_manifest_entry(spec, output_dir) for spec in MEDIA_SPECS]}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--duration", type=float, default=1.0)
    args = parser.parse_args()

    manifest = generate_all(args.output_dir, duration=args.duration)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
