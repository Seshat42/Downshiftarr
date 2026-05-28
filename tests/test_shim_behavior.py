import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.simulated]


def load_shim():
    path = Path(__file__).resolve().parents[1] / "Plex Transcoder"
    loader = importlib.machinery.SourceFileLoader("plex_transcoder_shim_for_tests", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shim_media(file_path, height, dynamic_range="SDR", stream_count=2):
    return {
        "height": height,
        "videoResolution": str(height),
        "videoDynamicRange": dynamic_range,
        "Part": [
            {
                "file": file_path,
                "Stream": [{"streamType": 1, "height": height}] + [{"streamType": 2} for _ in range(stream_count - 1)],
            }
        ],
    }


def test_shim_fallback_selection_prefers_sdr_1080(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)

    current = shim.build_media_info(shim_media("/media/movie-2160-hdr.mkv", 2160, "HDR"))
    item = {
        "Media": [
            current.media,
            shim_media("/media/movie-720-sdr.mkv", 720, "SDR"),
            shim_media("/media/movie-1080-sdr.mkv", 1080, "SDR"),
            shim_media("/media/movie-1080-hdr.mkv", 1080, "HDR"),
        ]
    }

    fallback = shim.pick_best_fallback(item, current, required_max_stream=None)

    assert fallback.file_path == "/media/movie-1080-sdr.mkv"
    assert fallback.dyn_range_class == "SDR"


def test_shim_rewrites_tonemap_filters_when_swapping_to_sdr(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "REMOVE_BITRATE_LIMITS", True)
    monkeypatch.setattr(shim, "STRIP_HDR_TONEMAP_FILTERS", True)

    args = [
        "-i",
        "/media/movie-2160-hdr.mkv",
        "-filter_complex",
        "[0:v]zscale=t=linear,tonemap=hable,format=yuv420p[v]",
        "-b:v",
        "12000k",
    ]

    rewritten = shim.rewrite_args_for_performance(args, input_value_index=1, swapped_to_sdr=True)

    assert "12000k" not in rewritten
    assert any("null" in arg for arg in rewritten)
    assert all("tonemap=hable" not in arg for arg in rewritten)
