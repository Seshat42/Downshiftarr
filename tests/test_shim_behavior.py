import importlib.machinery
import importlib.util
import json
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


def test_shim_uses_absolute_python_interpreter():
    path = Path(__file__).resolve().parents[1] / "Plex Transcoder"

    first_line = path.read_text(encoding="utf-8").splitlines()[0]

    assert first_line == "#!/usr/bin/python3"


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


def shim_media_with_edition(file_path, height, dynamic_range="SDR", edition=""):
    row = shim_media(file_path, height, dynamic_range)
    if edition:
        row["editionTitle"] = edition
    return row


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


def test_shim_fallback_selection_does_not_cross_plex_editions(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)

    current = shim.build_media_info(shim_media_with_edition("/media/movie {edition-Theatrical} - 2160p HDR.mkv", 2160, "HDR", "Theatrical"))
    item = {
        "Media": [
            current.media,
            shim_media_with_edition("/media/movie {edition-Director's Cut} - 1080p SDR.mkv", 1080, "SDR", "Director's Cut"),
        ]
    }

    assert shim.pick_best_fallback(item, current, required_max_stream=None) is None


def test_shim_fallback_selection_allows_same_plex_edition(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)

    current = shim.build_media_info(shim_media_with_edition("/media/movie {edition-Theatrical} - 2160p HDR.mkv", 2160, "HDR", "Theatrical"))
    item = {
        "Media": [
            current.media,
            shim_media_with_edition("/media/movie {edition-Theatrical} - 1080p SDR.mkv", 1080, "SDR", "Theatrical"),
            shim_media_with_edition("/media/movie {edition-Director's Cut} - 720p SDR.mkv", 720, "SDR", "Director's Cut"),
        ]
    }

    fallback = shim.pick_best_fallback(item, current, required_max_stream=None)

    assert fallback.file_path == "/media/movie {edition-Theatrical} - 1080p SDR.mkv"


def test_shim_fallback_selection_infers_sdr_from_filename_when_plex_metadata_is_thin(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)

    current = shim.build_media_info(shim_media("/media/movie-2160-hdr.mkv", 2160, "UNKNOWN"))
    item = {
        "Media": [
            current.media,
            shim_media("/media/movie-1080-sdr.mkv", 1080, "UNKNOWN"),
            shim_media("/media/movie-720-hdr.mkv", 720, "UNKNOWN"),
        ]
    }

    fallback = shim.pick_best_fallback(item, current, required_max_stream=None)

    assert fallback.file_path == "/media/movie-1080-sdr.mkv"
    assert fallback.dyn_range_class == "SDR"


def test_shim_media_info_infers_hdr_from_filename_when_plex_metadata_is_thin():
    shim = load_shim()

    info = shim.build_media_info(shim_media("/media/movie-1080-hdr10.mkv", 1080, "UNKNOWN"))

    assert info.dyn_range_class == "HDR"


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


def test_shim_intercepts_plex_hls_ssegment_output(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    captured = {}

    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    monkeypatch.setattr(shim, "ENABLE_CACHE", False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(
        shim.sys,
        "argv",
        [
            "Plex Transcoder",
            "-codec:0",
            "h264",
            "-codec:1",
            "truehd_eae",
            "-eae_prefix:1",
            "bragi-downshiftarr-test_",
            "-i",
            input_file,
            "-filter_complex",
            "[0:0]scale=w=480:h=270[0]",
            "-map",
            "[0]",
            "-codec:0",
            "libx264",
            "-segment_format",
            "mpegts",
            "-f",
            "ssegment",
            "-segment_list",
            "http://127.0.0.1:32400/video/:/transcode/session/example/manifest",
            "media-%05d.ts",
        ],
    )
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", {"Media": [shim_media(input_file, 2160, "HDR")]}))
    monkeypatch.setattr(
        shim,
        "plex_fetch_full_metadata",
        lambda rating_key: {
            "Media": [
                shim_media(input_file, 2160, "HDR"),
                shim_media(fallback_file, 1080, "SDR"),
            ]
        },
    )

    shim.main()

    assert captured["real"] == str(real)
    assert captured["args"][captured["args"].index("-i") + 1] == fallback_file
    assert "truehd_eae" not in captured["args"]
    assert "-eae_prefix:1" not in captured["args"]
    assert "libx264" in captured["args"]


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
    token_path = tmp_path / "plex-token"
    token_path.write_text("file-token\n", encoding="utf-8")
    token_path.chmod(0o600)
    config_path = tmp_path / "shim-config.json"
    config_path.write_text(
        """{
          "PLEX_URL": "http://10.67.0.2:32400",
          "PLEX_TOKEN_FILE": "%s",
          "PLEX_HTTP_TIMEOUT_S": 0.25,
          "CACHE_FILE": "/var/lib/downshiftarr/plex-transcoder-cache.json",
          "LOG_FILE": "/var/log/downshiftarr/plex-transcoder-shim.log",
          "KILL_TRANSCODE_IF_UNSURE": true,
          "REMOVE_BITRATE_LIMITS": true
        }"""
        % str(token_path).replace("\\", "\\\\"),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    shim = load_shim()

    assert shim.PLEX_URL == "http://10.67.0.2:32400"
    assert shim.PLEX_TOKEN_FILE == str(token_path)
    assert shim.effective_plex_token() == "file-token"
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


def test_shim_rejects_unsafe_token_file(monkeypatch, tmp_path):
    token_path = tmp_path / "plex-token"
    token_path.write_text("file-token\n", encoding="utf-8")
    token_path.chmod(0o606)
    config_path = tmp_path / "shim-config.json"
    config_path.write_text(
        '{"PLEX_TOKEN_FILE": "%s"}' % str(token_path).replace("\\", "\\\\"),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))
    monkeypatch.setenv("X_PLEX_TOKEN", "env-token")

    shim = load_shim()

    assert shim.effective_plex_token() == ""


def test_shim_rejects_symlink_token_file(monkeypatch, tmp_path):
    target = tmp_path / "plex-token"
    target.write_text("file-token\n", encoding="utf-8")
    target.chmod(0o600)
    link = tmp_path / "plex-token-link"
    link.symlink_to(target)
    config_path = tmp_path / "shim-config.json"
    config_path.write_text(
        '{"PLEX_TOKEN_FILE": "%s"}' % str(link).replace("\\", "\\\\"),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    shim = load_shim()

    assert shim.effective_plex_token() == ""


def test_shim_finds_file_with_section_scan_fallback(monkeypatch):
    shim = load_shim()
    calls = []
    target = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - Downshiftarr Canary - 2160p.mkv"

    def fake_get(path, params):
        calls.append((path, dict(params)))
        if path in {"/hubs/search", "/hubs/search/", "/search", "/search/"}:
            return {"MediaContainer": {"Hub": []}}
        if path == "/library/sections":
            return {
                "MediaContainer": {
                    "Directory": [
                        {"key": "1", "type": "movie", "Location": [{"path": "/mnt/media/Movies"}]},
                        {"key": "2", "type": "show", "Location": [{"path": "/mnt/media/Series"}]},
                    ]
                }
            }
        if path == "/library/sections/1/all":
            return {
                "MediaContainer": {
                    "Metadata": [
                        {
                            "ratingKey": "24",
                            "Media": [
                                {"Part": [{"file": target}]},
                            ],
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected Plex path {path}")

    monkeypatch.setattr(shim, "plex_get_json", fake_get)

    found = shim.plex_find_item_by_file(target)

    assert found is not None
    assert found[0] == "24"
    assert ("/library/sections/1/all", {}) in calls
    assert not any(path == "/library/sections/2/all" for path, _params in calls)


def test_shim_section_scan_uses_episode_type_for_show_libraries(monkeypatch):
    shim = load_shim()
    calls = []
    target = "/mnt/media/Series/Deli Boys (2025)/Season 02/Deli Boys - S02E01 - Downshiftarr Canary - 2160p.mkv"

    def fake_get(path, params):
        calls.append((path, dict(params)))
        if path in {"/hubs/search", "/hubs/search/", "/search", "/search/"}:
            return {"MediaContainer": {"Hub": []}}
        if path == "/library/sections":
            return {"MediaContainer": {"Directory": [{"key": "2", "type": "show", "Location": [{"path": "/mnt/media/Series"}]}]}}
        if path == "/library/sections/2/all":
            return {"MediaContainer": {"Metadata": [{"ratingKey": "44", "Media": [{"Part": [{"file": target}]}]}]}}
        raise AssertionError(f"unexpected Plex path {path}")

    monkeypatch.setattr(shim, "plex_get_json", fake_get)

    found = shim.plex_find_item_by_file(target)

    assert found is not None
    assert found[0] == "44"
    assert ("/library/sections/2/all", {"type": "4"}) in calls


def test_shim_uses_precomputed_version_index_before_plex_search(monkeypatch, tmp_path):
    target = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 2160p HDR.mkv"
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "items": [
                    {
                        "ratingKey": "9001",
                        "Media": [
                            {"height": 2160, "Part": [{"file": target}]},
                            {"height": 1080, "Part": [{"file": "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 1080p SDR.mkv"}]},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    index_path.chmod(0o660)
    config_path = tmp_path / "shim-config.json"
    config_path.write_text(
        json.dumps({"VERSION_INDEX_FILE": str(index_path)}),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))
    shim = load_shim()
    monkeypatch.setattr(shim, "plex_get_json", lambda path, params: (_ for _ in ()).throw(AssertionError(path)))

    found = shim.plex_find_item_by_file(target)

    assert found is not None
    assert found[0] == "9001"


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
