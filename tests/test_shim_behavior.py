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


def test_shim_fallback_selection_includes_360p_waterfall(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)

    current = shim.build_media_info(shim_media("/media/movie-480-sdr.mkv", 480, "SDR"))
    item = {
        "Media": [
            shim_media("/media/movie-1080-sdr.mkv", 1080, "SDR"),
            shim_media("/media/movie-480-sdr.mkv", 480, "SDR"),
            shim_media("/media/movie-360-sdr.mkv", 360, "SDR"),
        ]
    }

    fallback = shim.pick_best_fallback(item, current, required_max_stream=None)

    assert fallback.file_path == "/media/movie-360-sdr.mkv"


def test_shim_waterfalls_unprotected_transcode_to_lower_version(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    captured = {}

    input_file = "/media/movie-1080-sdr.mkv"
    monkeypatch.setattr(shim, "ENABLE_CACHE", False)
    monkeypatch.setattr(shim, "AUTO_WATERFALL_ON_CONTINUED_TRANSCODE", True)
    monkeypatch.setattr(shim, "WATERFALL_MIN_HEIGHT", 360)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", {"Media": [shim_media(input_file, 1080, "SDR")]}))
    monkeypatch.setattr(
        shim,
        "plex_fetch_full_metadata",
        lambda rating_key: {
            "Media": [
                shim_media(input_file, 1080, "SDR"),
                shim_media("/media/movie-720-sdr.mkv", 720, "SDR"),
                shim_media("/media/movie-360-sdr.mkv", 360, "SDR"),
            ]
        },
    )

    shim.main()

    assert captured["real"] == str(real)
    assert captured["args"][1] == "/media/movie-720-sdr.mkv"


def test_shim_passes_through_when_continued_waterfall_has_no_lower_version(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    captured = {}

    input_file = "/media/movie-360-sdr.mkv"
    monkeypatch.setattr(shim, "ENABLE_CACHE", False)
    monkeypatch.setattr(shim, "AUTO_WATERFALL_ON_CONTINUED_TRANSCODE", True)
    monkeypatch.setattr(shim, "WATERFALL_MIN_HEIGHT", 360)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", {"Media": [shim_media(input_file, 360, "SDR")]}))

    shim.main()

    assert captured["args"][1] == input_file


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


def test_shim_loads_external_json_config_before_runtime(monkeypatch, tmp_path):
    config_path = tmp_path / "shim-config.json"
    config_path.write_text(
        """{
          "PLEX_URL": "http://10.67.0.2:32400",
          "PLEX_HTTP_TIMEOUT_S": 0.25,
          "CACHE_FILE": "/var/lib/downshiftarr/plex-transcoder-cache.json",
          "LOG_FILE": "/var/log/downshiftarr/plex-transcoder-shim.log",
          "KILL_TRANSCODE_IF_UNSURE": true,
          "REMOVE_BITRATE_LIMITS": true
        }""",
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    shim = load_shim()

    assert shim.PLEX_URL == "http://10.67.0.2:32400"
    assert shim.PLEX_HTTP_TIMEOUT_S == 0.25
    assert shim.CACHE_FILE == "/var/lib/downshiftarr/plex-transcoder-cache.json"
    assert shim.LOG_FILE == "/var/log/downshiftarr/plex-transcoder-shim.log"
    assert shim.KILL_TRANSCODE_IF_UNSURE is True
    assert shim.REMOVE_BITRATE_LIMITS is True


def test_shim_rejects_unknown_external_config_keys(monkeypatch, tmp_path):
    config_path = tmp_path / "shim-config.json"
    config_path.write_text('{"PLEX_URL": "http://127.0.0.1:32400", "UNREVIEWED_FLAG": true}', encoding="utf-8")
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    with pytest.raises(RuntimeError, match="Unsupported shim config key"):
        load_shim()


def test_shim_rejects_wrong_external_config_value_types(monkeypatch, tmp_path):
    config_path = tmp_path / "shim-config.json"
    config_path.write_text('{"PLEX_HTTP_TIMEOUT_S": "slow"}', encoding="utf-8")
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    with pytest.raises(RuntimeError, match="PLEX_HTTP_TIMEOUT_S must be numeric"):
        load_shim()


def test_shim_rejects_relative_external_config_path(monkeypatch):
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", "shim-config.json")

    with pytest.raises(RuntimeError, match="path must be absolute"):
        load_shim()


def test_shim_rejects_symlink_external_config(monkeypatch, tmp_path):
    target = tmp_path / "shim-config.json"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o600)
    link = tmp_path / "shim-config-link.json"
    link.symlink_to(target)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(link))

    with pytest.raises(RuntimeError, match="symlink|opened safely"):
        load_shim()


def test_shim_rejects_group_or_world_writable_external_config(monkeypatch, tmp_path):
    config_path = tmp_path / "shim-config.json"
    config_path.write_text("{}", encoding="utf-8")
    config_path.chmod(0o666)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    with pytest.raises(RuntimeError, match="writable by group or other"):
        load_shim()


def test_shim_rejects_empty_external_transcoder_suffix(monkeypatch, tmp_path):
    config_path = tmp_path / "shim-config.json"
    config_path.write_text('{"REAL_TRANSCODER_SUFFIX": ""}', encoding="utf-8")
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    with pytest.raises(RuntimeError, match="REAL_TRANSCODER_SUFFIX must not be empty"):
        load_shim()


def test_shim_never_resolves_to_undiverted_transcoder(monkeypatch, tmp_path):
    shim = load_shim()
    shim_path = tmp_path / "Plex Transcoder"
    monkeypatch.setattr(shim, "REAL_TRANSCODER_PATH", "")
    monkeypatch.setattr(shim.sys, "argv", [str(shim_path)])

    real_exists = {"/usr/lib/plexmediaserver/Plex Transcoder": True}
    monkeypatch.setattr(shim.os.path, "exists", lambda path: real_exists.get(path, False))
    monkeypatch.setattr(shim.os, "access", lambda path, mode: real_exists.get(path, False))

    assert shim.resolve_real_transcoder_path() == str(shim_path) + "_REAL"


def test_shim_rejects_suffix_candidate_self_reference(monkeypatch, tmp_path):
    shim = load_shim()
    shim_path = tmp_path / "Plex Transcoder"
    shim_path.write_text("# shim\n", encoding="utf-8")
    monkeypatch.setattr(shim.sys, "argv", [str(shim_path)])
    monkeypatch.setattr(shim, "REAL_TRANSCODER_PATH", "")
    monkeypatch.setattr(shim, "REAL_TRANSCODER_SUFFIX", "")

    with pytest.raises(RuntimeError, match="suffix must not resolve"):
        shim.resolve_real_transcoder_path()


def test_shim_rejects_explicit_real_transcoder_self_reference(monkeypatch, tmp_path):
    shim = load_shim()
    shim_path = tmp_path / "Plex Transcoder"
    shim_path.write_text("# shim\n", encoding="utf-8")
    monkeypatch.setattr(shim.sys, "argv", [str(shim_path)])
    monkeypatch.setattr(shim, "REAL_TRANSCODER_PATH", str(shim_path))

    with pytest.raises(RuntimeError, match="must not resolve to the shim itself"):
        shim.resolve_real_transcoder_path()
