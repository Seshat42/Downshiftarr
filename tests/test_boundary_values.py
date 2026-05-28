from __future__ import annotations

import pytest

import Downshiftarr
from tests.harness.fakes import attr, media
from tests.harness.shim_loader import load_shim

pytestmark = [pytest.mark.boundary]


@pytest.mark.parametrize(
    ("height", "dynamic_range", "expected"),
    [
        (1999, "SDR", False),
        (2000, "SDR", True),
        (2001, "SDR", True),
        (None, "HDR", True),
        (0, "UNKNOWN", False),
        (-1, "SDR", False),
    ],
)
def test_high_quality_boundary_values(monkeypatch, height, dynamic_range, expected):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 2000)

    assert Downshiftarr.is_high_quality(height, dynamic_range) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        ("0", None),
        ("-1", None),
        ("480", 480),
        ("sd", None),
        ("4k", 2160),
        ("4k movie", None),
        ("2160p.remux", 2160),
        ("999999999999999999999999", 999999999999999999999999),
    ],
)
def test_downshiftarr_resolution_boundaries(raw, expected):
    assert Downshiftarr.parse_resolution_hint(raw) == expected


def test_fallback_selection_equal_height_sdr_improves_hdr(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 2000)
    item = attr(
        media=[
            media("current", 1080, "HDR", selected=True),
            media("same-height-sdr", 1080, "SDR"),
            media("lower-hdr", 720, "HDR"),
        ]
    )

    assert Downshiftarr.pick_best_fallback_media_index(item, "current", 1080, "HDR") == 1


def test_shim_stream_index_compatibility_boundary(monkeypatch):
    shim = load_shim("plex_transcoder_shim_boundary")
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", True)

    current = shim.build_media_info(
        {
            "height": 2160,
            "videoDynamicRange": "HDR",
            "Part": [{"file": "/movie-2160.mkv", "Stream": [{"streamType": 1, "index": 0}, {"streamType": 2, "index": 1}]}],
        }
    )
    full_item = {
        "Media": [
            current.media,
            {
                "height": 1080,
                "videoDynamicRange": "SDR",
                "Part": [{"file": "/movie-1080-one-stream.mkv", "Stream": [{"streamType": 1, "index": 0}]}],
            },
            {
                "height": 720,
                "videoDynamicRange": "SDR",
                "Part": [{"file": "/movie-720-two-streams.mkv", "Stream": [{"streamType": 1, "index": 0}, {"streamType": 2, "index": 1}]}],
            },
        ]
    }

    fallback = shim.pick_best_fallback(full_item, current, required_max_stream=1)

    assert fallback.file_path == "/movie-720-two-streams.mkv"


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["-i", "/media/movie.MKV", "-f", "dash"], ("/media/movie.MKV", 1)),
        (["-i"], (None, -1)),
        (["-i", "pipe:0", "-i", "/media/movie.webm"], ("/media/movie.webm", 3)),
        (["-i", "/media/audio.mp3"], (None, -1)),
    ],
)
def test_shim_primary_input_boundaries(args, expected):
    shim = load_shim("plex_transcoder_shim_primary_input")

    assert shim.find_primary_input(args) == expected
