import importlib.machinery
import importlib.util
import json
import sys
import time
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


def shim_media_with_bitrate(file_path, height, bitrate, dynamic_range="SDR"):
    row = shim_media(file_path, height, dynamic_range)
    row["bitrate"] = bitrate
    row["videoBitrate"] = bitrate
    return row


def shim_media_with_edition(file_path, height, dynamic_range="SDR", edition=""):
    row = shim_media(file_path, height, dynamic_range)
    if edition:
        row["editionTitle"] = edition
    return row


def shim_media_with_streams(file_path, height, dynamic_range="SDR", streams=None):
    row = shim_media(file_path, height, dynamic_range, stream_count=1)
    row["Part"][0]["Stream"] = [{"streamType": 1, "height": height}] + list(streams or [])
    return row


def compact_v2_index(target_file, fallback_file, *, target_height=2160, fallback_height=1080, rating_key="9001"):
    return {
        "version": 2,
        "generated_at_epoch": int(time.time()),
        "paths": {
            target_file: {
                "rating_key": rating_key,
                "edition_key": "",
                "versions": [
                    {
                        "file": target_file,
                        "height": target_height,
                        "dynamic_range": "HDR",
                        "bitrate_kbps": 58000,
                        "max_stream_index": 1,
                        "edition_key": "",
                    },
                    {
                        "file": fallback_file,
                        "height": fallback_height,
                        "dynamic_range": "SDR",
                        "bitrate_kbps": 12000,
                        "max_stream_index": 1,
                        "edition_key": "",
                    },
                ],
            }
        },
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


def test_shim_default_protected_height_is_anything_above_1080():
    shim = load_shim()

    assert shim.PROTECTED_SOURCE_MIN_HEIGHT == 1081
    assert not shim.is_protected_height(1080)
    assert shim.is_protected_height(1081)
    assert shim.is_protected_height(1440)
    assert shim.is_protected_height(2160)
    assert shim.VERSION_INDEX_MAX_AGE_S == 60
    assert shim.CACHE_TTL_S == 60


def test_shim_exposes_fast_protected_waterfall_entrypoint():
    shim = load_shim()

    assert callable(shim.protected_waterfall_decision)
    assert callable(shim.attempt_protected_waterfall_fast_path)


def test_shim_identifies_1080_remux_by_configured_bitrate():
    shim = load_shim()
    current = shim.build_media_info(shim_media_with_bitrate("/media/movie-1080-sdr.mkv", 1080, 25_000, "SDR"))
    ordinary = shim.build_media_info(shim_media_with_bitrate("/media/movie-1080-sdr-small.mkv", 1080, 12_000, "SDR"))

    assert shim.REMUX_1080_MIN_BITRATE_KBPS == 25_000
    assert shim.is_1080_remux_like(current)
    assert not shim.is_1080_remux_like(ordinary)


def test_shim_does_not_use_generic_cache_before_actual_height_proof(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = tmp_path / "movie-open-matte-source.mkv"
    cached_fallback = tmp_path / "stale-cross-edition-cache.mkv"
    input_file.write_text("source\n", encoding="utf-8")
    cached_fallback.write_text("stale fallback\n", encoding="utf-8")
    cache_path = tmp_path / "cache.json"
    index_path = tmp_path / "plex-version-index.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    str(input_file): {
                        "ts": shim.time.time(),
                        "rating_key": "rk-stale",
                        "fallback_file": str(cached_fallback),
                        "fallback_height": 720,
                        "fallback_dr": "SDR",
                        "fallback_max_stream_index": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    index_path.write_text(
        json.dumps(compact_v2_index(str(input_file), str(cached_fallback), target_height=1440, fallback_height=720, rating_key="rk-1")),
        encoding="utf-8",
    )

    monkeypatch.setattr(shim, "CACHE_FILE", str(cache_path), raising=False)
    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", True, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_NO_FALLBACK", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_fetch_full_metadata", lambda rating_key: {"Media": [shim_media(str(input_file), 1440, "SDR")]})
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", str(input_file), "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("generic cache must not bypass actual-height protected proof")),
    )

    with pytest.raises(SystemExit):
        shim.main()


def test_shim_blocks_cinematic_4kish_source_without_verified_fallback(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = "/media/movie-1440-sdr.mkv"

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_NO_FALLBACK", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", {"Media": [shim_media(input_file, 1440, "SDR")]}))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError(">1080 protected transcode must not pass through")),
    )

    with pytest.raises(SystemExit):
        shim.main()


def test_shim_uses_live_lookup_for_protected_index_miss(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": int(shim.time.time()),
                "paths": {
                    "/media/other.mkv": {
                        "rating_key": "other",
                        "versions": [{"file": "/media/other.mkv", "height": 1080, "dynamic_range": "SDR"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}
    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    current_media = shim_media(input_file, 2160, "HDR")
    full_item = {"Media": [current_media, shim_media(fallback_file, 1080, "SDR")]}

    def fake_get_json(path, params):
        if path == "/library/sections":
            return {"MediaContainer": {"Directory": [{"key": "1", "type": "movie", "Location": [{"path": "/media"}]}]}}
        if path == "/library/sections/1/all":
            return {"MediaContainer": {"Metadata": [{"ratingKey": "rk-1", "Media": [current_media]}]}}
        if path == "/library/metadata/rk-1":
            return {"MediaContainer": {"Metadata": [full_item]}}
        return None

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_NO_FALLBACK", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_get_json", fake_get_json)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][captured["args"].index("-i") + 1] == fallback_file
    assert shim.VERSION_INDEX_LAST_STATUS == "miss"


def test_shim_uses_live_lookup_for_stale_protected_index(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index.json"
    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": int(shim.time.time()) - 3600,
                "paths": {
                    input_file: {
                        "rating_key": "rk-1",
                        "versions": [{"file": input_file, "height": 2160, "dynamic_range": "HDR"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}
    full_item = {"Media": [shim_media(input_file, 2160, "HDR"), shim_media(fallback_file, 1080, "SDR")]}

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "VERSION_INDEX_MAX_AGE_S", 60, raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_find_item_by_file_via_sections", lambda path: ("rk-1", full_item))
    monkeypatch.setattr(shim, "plex_fetch_full_metadata", lambda rating_key: full_item)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][captured["args"].index("-i") + 1] == fallback_file


def test_shim_1080_hdr_no_fallback_passes_through_by_default(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    captured = {}
    input_file = "/media/movie-1080-hdr.mkv"

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_NO_FALLBACK", True, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", {"Media": [shim_media(input_file, 1080, "HDR")]}))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][captured["args"].index("-i") + 1] == input_file


def test_shim_can_hard_protect_1080_remux_when_configured(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = "/media/movie-1080-remux-sdr.mkv"

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "HARD_PROTECT_1080_REMUX", True, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_NO_FALLBACK", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", {"Media": [shim_media(input_file, 1080, "SDR")]}))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("configured 1080 remux hard protection must not pass through")),
    )

    with pytest.raises(SystemExit):
        shim.main()


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


def test_shim_fallback_selection_prefers_client_friendly_audio_and_subtitles(monkeypatch):
    shim = load_shim()
    monkeypatch.setattr(shim, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(shim, "MAX_FALLBACK_HEIGHT", 1080)
    monkeypatch.setattr(shim, "FALLBACK_SDR_ONLY", True)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)

    current = shim.build_media_info(shim_media("/media/movie-2160-hdr.mkv", 2160, "HDR"))
    item = {
        "Media": [
            current.media,
            shim_media_with_streams(
                "/media/movie-1080-sdr-truehd-pgs.mkv",
                1080,
                "SDR",
                [
                    {"streamType": 2, "codec": "truehd", "channels": 8},
                    {"streamType": 3, "codec": "pgs", "forced": True},
                ],
            ),
            shim_media_with_streams(
                "/media/movie-1080-sdr-aac-srt.mkv",
                1080,
                "SDR",
                [
                    {"streamType": 2, "codec": "aac", "channels": 2},
                    {"streamType": 3, "codec": "srt", "forced": False},
                ],
            ),
        ]
    }

    fallback = shim.pick_best_fallback(item, current, required_max_stream=None)

    assert fallback.file_path == "/media/movie-1080-sdr-aac-srt.mkv"


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
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(json.dumps(compact_v2_index(input_file, fallback_file, rating_key="rk-1")), encoding="utf-8")
    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
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


def test_shim_budget_exhaustion_passes_through_without_plex_lookup(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    captured = {}

    input_file = "/media/movie-1080-sdr.mkv"
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 0, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", True)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))
    monkeypatch.setattr(
        shim,
        "plex_get_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("budget-exhausted shim must not call Plex API")),
    )

    shim.main()

    assert captured["real"] == str(real)
    assert captured["args"] == ["-i", input_file, "-f", "dash", "chunk"]


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


def test_shim_uses_precomputed_version_index_before_section_lookup(monkeypatch, tmp_path):
    target = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 2160p HDR.mkv"
    fallback = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 1080p SDR.mkv"
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(json.dumps(compact_v2_index(target, fallback)), encoding="utf-8")
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


def test_shim_uses_compact_v2_version_index_before_section_lookup(monkeypatch, tmp_path):
    shim = load_shim()
    target = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 2160p HDR.mkv"
    fallback = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 1080p SDR.mkv"
    index_path = tmp_path / "plex-version-index-v2.json"
    index_path.write_text(json.dumps(compact_v2_index(target, fallback)), encoding="utf-8")
    index_path.chmod(0o660)

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "plex_get_json", lambda path, params: (_ for _ in ()).throw(AssertionError(path)))

    found = shim.plex_find_item_by_file(target)

    assert found is not None
    rating_key, item = found
    assert rating_key == "9001"
    assert shim.VERSION_INDEX_LAST_STATUS == "hit_v2"
    current = shim.find_current_media(item, target)
    best = shim.pick_best_fallback(item, current, required_max_stream=1)
    assert current.height == 2160
    assert best.file_path == fallback
    assert best.height == 1080


def test_shim_rejects_legacy_non_v2_version_index_without_v1_mode(monkeypatch, tmp_path):
    shim = load_shim()
    target = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 2160p HDR.mkv"
    fallback = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 1080p SDR.mkv"
    index_path = tmp_path / "plex-version-index-v1.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at_epoch": int(time.time()),
                "items": [
                    {
                        "ratingKey": "9001",
                        "Media": [
                            shim_media(target, 2160, "HDR"),
                            shim_media(fallback, 1080, "SDR"),
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)

    found = shim.plex_find_item_by_file_via_version_index(target)

    assert found is None
    assert shim.VERSION_INDEX_LAST_STATUS == "invalid"
    assert "unsupported_v1" not in (Path(__file__).resolve().parents[1] / "Plex Transcoder").read_text(encoding="utf-8")


def test_shim_uses_plex_metadata_api_even_after_v2_locator_hit(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index-v2.json"
    input_file = "/media/movie-2160-hdr.mkv"
    stale_index_fallback = "/media/index-only-1080-sdr.mkv"
    authoritative_fallback = "/media/api-1080-sdr.mkv"
    index_path.write_text(json.dumps(compact_v2_index(input_file, stale_index_fallback)), encoding="utf-8")
    captured = {}
    calls = []

    def fake_get_json(path, params):
        calls.append((path, dict(params or {})))
        if path == "/library/metadata/9001":
            return {
                "MediaContainer": {
                    "Metadata": [
                        {
                            "ratingKey": "9001",
                            "Media": [
                                shim_media(input_file, 2160, "HDR"),
                                shim_media(authoritative_fallback, 1080, "SDR"),
                            ],
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected Plex API path: {path}")

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_get_json", fake_get_json)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert calls == [("/library/metadata/9001", {})]
    assert captured["args"][captured["args"].index("-i") + 1] == authoritative_fallback


def test_shim_retries_protected_metadata_lookup_once_after_v2_locator_hit(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index-v2.json"
    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    index_path.write_text(json.dumps(compact_v2_index(input_file, fallback_file, rating_key="9001")), encoding="utf-8")
    captured = {}
    calls = []

    def fake_fetch_full_metadata(rating_key):
        calls.append(rating_key)
        if len(calls) == 1:
            return None
        return {"Media": [shim_media(input_file, 2160, "HDR"), shim_media(fallback_file, 1080, "SDR")]}

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_fetch_full_metadata", fake_fetch_full_metadata)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert calls == ["9001", "9001"]
    assert captured["args"][captured["args"].index("-i") + 1] == fallback_file


def test_shim_does_not_use_basename_search_to_authorize_lookup(monkeypatch, tmp_path):
    shim = load_shim()
    input_file = "/media/movie-2160-hdr.mkv"
    index_path = tmp_path / "missing-index.json"

    def fake_get_json(path, params):
        if path.startswith("/hubs/search") or path.startswith("/search"):
            raise AssertionError("basename search must not authorize protected swaps")
        if path == "/library/sections":
            return {"MediaContainer": {"Directory": []}}
        return None

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ALLOW_LIVE_LOOKUP_ON_INDEX_MISS", True, raising=False)
    monkeypatch.setattr(shim, "plex_get_json", fake_get_json)

    assert shim.plex_find_item_by_file(input_file) is None


def test_shim_version_index_reports_empty_and_stale(monkeypatch, tmp_path):
    shim = load_shim()
    target = "/mnt/media/Movies/WALL-E (2008)/WALL-E (2008) - 2160p HDR.mkv"
    index_path = tmp_path / "plex-version-index.json"
    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path))

    index_path.write_text(json.dumps({"version": 2, "paths": {}}), encoding="utf-8")
    assert shim.plex_find_item_by_file_via_version_index(target) is None
    assert shim.VERSION_INDEX_LAST_STATUS == "empty"

    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": 1000,
                "paths": {
                    target: {
                        "rating_key": "9001",
                        "versions": [{"file": target, "height": 2160, "dynamic_range": "HDR"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(shim, "VERSION_INDEX_MAX_AGE_S", 60, raising=False)
    monkeypatch.setattr(shim.time, "time", lambda: 2000)

    assert shim.plex_find_item_by_file_via_version_index(target) is None
    assert shim.VERSION_INDEX_LAST_STATUS == "stale"


def test_shim_rejects_unsafe_numeric_config_ranges(monkeypatch, tmp_path):
    config_path = tmp_path / "shim-config.json"
    config_path.write_text(
        json.dumps(
            {
                "PROTECTED_SOURCE_MIN_HEIGHT": 0,
                "PROTECTED_LOOKUP_RETRY_ATTEMPTS": -1,
                "PROTECTED_LOOKUP_RETRY_DELAY_MS": -1,
                "DECISION_BUDGET_MS": 0,
                "CACHE_TTL_S": -1,
                "REMUX_1080_MIN_BITRATE_KBPS": -10,
            }
        ),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    monkeypatch.setenv("DOWNSHIFTARR_SHIM_CONFIG", str(config_path))

    with pytest.raises(RuntimeError, match="outside safe range"):
        load_shim()


def test_shim_records_sanitized_aggregate_telemetry(monkeypatch, tmp_path):
    shim = load_shim()
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)

    shim.record_telemetry("waterfall_swap", elapsed_ms=12.4)

    text = telemetry_path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["version"] == 1
    assert data["outcomes"]["waterfall_swap"]["count"] == 1
    assert data["latency_ms"]["count"] == 1
    assert "client_families" not in data
    assert "latency_by_client_family" not in data
    assert "Alice" not in text
    assert "Plex for Roku" not in text


def test_shim_telemetry_records_global_percentiles_without_device_family(monkeypatch, tmp_path):
    shim = load_shim()
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)

    for value in (5.0, 12.0, 30.0, 90.0):
        shim.record_telemetry("cache_swap", elapsed_ms=value, index_status="hit")

    text = telemetry_path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["latency_ms"]["count"] == 4
    assert data["latency_ms"]["p95"] == 90.0
    assert data["version_index"]["hit"]["count"] == 4
    assert "client_families" not in data
    assert "latency_by_client_family" not in data
    assert "Alice" not in text


def test_shim_cache_loader_refuses_oversized_cache_without_delay(monkeypatch, tmp_path):
    shim = load_shim()
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(" " * (shim.MAX_CACHE_BYTES + 1), encoding="utf-8")
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    monkeypatch.setattr(shim, "CACHE_FILE", str(cache_path), raising=False)
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)

    loaded = shim._load_cache()

    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert loaded == {}
    assert data["outcomes"]["cache_oversized"]["count"] == 1


def test_shim_caps_plex_http_timeout_to_remaining_decision_budget(monkeypatch):
    shim = load_shim()
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"MediaContainer": {}}'

    monkeypatch.setattr(shim, "PLEX_TOKEN", "token", raising=False)
    monkeypatch.setattr(shim, "PLEX_TOKEN_FILE", "", raising=False)
    monkeypatch.setattr(shim, "PLEX_HTTP_TIMEOUT_S", 10.0, raising=False)
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 100, raising=False)
    monkeypatch.setattr(shim, "_ACTIVE_DECISION_START_MS", 1000.0, raising=False)
    monkeypatch.setattr(shim, "monotonic_ms", lambda: 1075.0)

    def fake_urlopen(req, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(shim.urllib.request, "urlopen", fake_urlopen)

    assert shim.plex_get_json("/status", {}) == {"MediaContainer": {}}
    assert 0 < captured["timeout"] <= 0.025


def test_shim_passes_through_when_budget_exhausted_before_http(monkeypatch):
    shim = load_shim()

    monkeypatch.setattr(shim, "PLEX_TOKEN", "token", raising=False)
    monkeypatch.setattr(shim, "PLEX_TOKEN_FILE", "", raising=False)
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 100, raising=False)
    monkeypatch.setattr(shim, "_ACTIVE_DECISION_START_MS", 1000.0, raising=False)
    monkeypatch.setattr(shim, "monotonic_ms", lambda: 1101.0)
    monkeypatch.setattr(
        shim.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("budget-exhausted request should not be opened")),
    )

    assert shim.plex_get_json("/status", {}) is None


def test_shim_shadow_mode_records_candidate_without_swapping(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    captured = {}

    input_file = "/media/movie-1080-sdr.mkv"
    fallback_file = "/media/movie-720-sdr.mkv"
    full_item = {"Media": [shim_media(input_file, 1080, "SDR"), shim_media(fallback_file, 720, "SDR")]}

    monkeypatch.setattr(shim, "SHADOW_MODE", True, raising=False)
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: ("rk-1", full_item))
    monkeypatch.setattr(shim, "plex_fetch_full_metadata", lambda rating_key: full_item)

    shim.main()

    assert captured["args"] == ["-i", input_file, "-f", "dash", "chunk"]
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert data["outcomes"]["shadow_swap_candidate"]["count"] == 1


def test_shim_downshift_first_uses_bounded_live_lookup_after_index_miss(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": int(shim.time.time()),
                "paths": {
                    "/media/other.mkv": {
                        "rating_key": "other",
                        "versions": [{"file": "/media/other.mkv", "height": 1080, "dynamic_range": "SDR"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    input_file = "/media/movie-1080-sdr.mkv"
    fallback_file = "/media/movie-720-sdr.mkv"
    current_media = shim_media(input_file, 1080, "SDR")
    full_item = {"Media": [current_media, shim_media(fallback_file, 720, "SDR")]}

    def fake_get_json(path, params):
        if path == "/library/sections":
            return {"MediaContainer": {"Directory": [{"key": "1", "type": "movie", "Location": [{"path": "/media"}]}]}}
        if path == "/library/sections/1/all":
            return {"MediaContainer": {"Metadata": [{"ratingKey": "rk-1", "Media": [current_media]}]}}
        if path == "/library/metadata/rk-1":
            return {"MediaContainer": {"Metadata": [full_item]}}
        return None

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_NO_FALLBACK", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_get_json", fake_get_json)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][1] == fallback_file
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert data["outcomes"]["live_lookup_waterfall_swap"]["count"] == 1
    assert data["version_index"]["miss"]["count"] == 1


def test_shim_live_lookup_index_miss_passes_through_when_budget_expires(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": int(shim.time.time()),
                "paths": {
                    "/media/other.mkv": {
                        "rating_key": "other",
                        "versions": [{"file": "/media/other.mkv", "height": 1080, "dynamic_range": "SDR"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}
    ticks = iter([1000.0, 1000.0, 1101.0, 1101.0, 1101.0])

    input_file = "/media/movie-1080-sdr.mkv"

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "PLEX_TOKEN", "token", raising=False)
    monkeypatch.setattr(shim, "PLEX_TOKEN_FILE", "", raising=False)
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 100, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "monotonic_ms", lambda: next(ticks, 1101.0))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))
    monkeypatch.setattr(
        shim.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("budget-expired live lookup should not open HTTP")),
    )

    shim.main()

    assert captured["args"][1] == input_file


def test_shim_blocks_4k_when_index_miss_budget_expires(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": int(shim.time.time()),
                "paths": {
                    "/media/other.mkv": {
                        "rating_key": "other",
                        "versions": [{"file": "/media/other.mkv", "height": 1080, "dynamic_range": "SDR"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    ticks = iter([1000.0, 1000.0, 1101.0, 1101.0, 1101.0])
    input_file = "/media/movie-2160-hdr.mkv"

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "PLEX_TOKEN", "token", raising=False)
    monkeypatch.setattr(shim, "PLEX_TOKEN_FILE", "", raising=False)
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 100, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "monotonic_ms", lambda: next(ticks, 1101.0))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("4K transcode must not pass through")),
    )
    monkeypatch.setattr(
        shim.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("budget-expired live lookup should not open HTTP")),
    )

    with pytest.raises(SystemExit):
        shim.main()


def test_shim_blocks_4k_when_lookup_uncertain_even_if_unsure_kill_disabled(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = "/media/movie-2160-hdr.mkv"

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: None)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("4K transcode must not pass through")),
    )

    with pytest.raises(SystemExit):
        shim.main()


def test_shim_blocks_4k_when_version_index_is_stale(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index.json"
    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    index_path.write_text(
        json.dumps(
            {
                "version": 2,
                "generated_at_epoch": int(shim.time.time()) - 3600,
                "paths": {
                    input_file: {
                        "rating_key": "rk-1",
                        "versions": [
                            {"file": input_file, "height": 2160, "dynamic_range": "HDR"},
                            {"file": fallback_file, "height": 1080, "dynamic_range": "SDR"},
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "VERSION_INDEX_MAX_AGE_S", 900, raising=False)
    monkeypatch.setattr(shim, "ALLOW_LIVE_LOOKUP_ON_INDEX_MISS", False, raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("4K transcode must not pass through")),
    )

    with pytest.raises(SystemExit):
        shim.main()


def test_shim_blocks_4k_cache_hit_without_fresh_version_index(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = tmp_path / "movie-2160-hdr.mkv"
    fallback_file = tmp_path / "movie-1080-sdr.mkv"
    input_file.write_text("source\n", encoding="utf-8")
    fallback_file.write_text("fallback\n", encoding="utf-8")
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                str(input_file): {
                    "ts": shim.time.time(),
                    "rating_key": "rk-1",
                    "fallback_file": str(fallback_file),
                    "fallback_height": 1080,
                    "fallback_dr": "SDR",
                    "fallback_max_stream_index": 1,
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(shim, "CACHE_FILE", str(cache_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", True, raising=False)
    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(tmp_path / "missing-index.json"), raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", str(input_file), "-f", "dash", "chunk"])
    monkeypatch.setattr(
        shim,
        "exec_real_transcoder",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("4K cache-only swap must not bypass fresh index")),
    )

    with pytest.raises(SystemExit):
        shim.main()


def test_shim_shadow_mode_swaps_4k_when_fresh_index_proves_fallback(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    index_path = tmp_path / "plex-version-index.json"
    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    index_path.write_text(json.dumps(compact_v2_index(input_file, fallback_file, rating_key="rk-1")), encoding="utf-8")
    captured = {}

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "SHADOW_MODE", True, raising=False)
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(
        shim,
        "plex_fetch_full_metadata",
        lambda rating_key: {"Media": [shim_media(input_file, 2160, "HDR"), shim_media(fallback_file, 1080, "SDR")]},
    )
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][1] == fallback_file
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert data["outcomes"]["waterfall_swap"]["count"] == 1


def test_shim_passes_through_if_budget_expires_during_lookup_even_when_strict(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    captured = {}
    ticks = iter([1000.0, 1000.0, 1101.0, 1101.0])

    input_file = "/media/movie-1080-sdr.mkv"

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 100, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", True, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "monotonic_ms", lambda: next(ticks, 1101.0))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: None)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][1] == input_file


def test_shim_blocks_unknown_actual_height_before_passthrough(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = "/media/Neutral Name.mkv"
    captured = {"exec_called": False}

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: None)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"exec_called": True}))

    with pytest.raises(SystemExit) as exc:
        shim.main()

    assert exc.value.code == 1
    assert captured["exec_called"] is False


def test_shim_blocks_unknown_actual_height_on_budget_exhaustion(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    input_file = "/media/Neutral Name.mkv"
    captured = {"exec_called": False}
    ticks = iter([1000.0, 1000.0, 1101.0, 1101.0])

    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "DECISION_BUDGET_MS", 100, raising=False)
    monkeypatch.setattr(shim, "KILL_TRANSCODE_IF_UNSURE", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(shim, "monotonic_ms", lambda: next(ticks, 1101.0))
    monkeypatch.setattr(shim, "plex_find_item_by_file", lambda path: None)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"exec_called": True}))

    with pytest.raises(SystemExit) as exc:
        shim.main()

    assert exc.value.code == 1
    assert captured["exec_called"] is False


def test_shim_version_index_hit_with_sibling_metadata_still_fetches_live_metadata(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    index_path = tmp_path / "plex-version-index.json"
    input_file = "/media/movie-2160-hdr.mkv"
    fallback_file = "/media/movie-1080-sdr.mkv"
    index_path.write_text(json.dumps(compact_v2_index(input_file, fallback_file, rating_key="rk-1")), encoding="utf-8")
    captured = {}
    calls = []

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))

    def fake_fetch_full_metadata(rating_key):
        calls.append(rating_key)
        return {"Media": [shim_media(input_file, 2160, "HDR"), shim_media(fallback_file, 1080, "SDR")]}

    monkeypatch.setattr(shim, "plex_fetch_full_metadata", fake_fetch_full_metadata)
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][1] == fallback_file
    assert calls == ["rk-1"]


def test_shim_v2_locator_hit_records_index_backed_continued_waterfall(monkeypatch, tmp_path):
    shim = load_shim()
    real = tmp_path / "Plex Transcoder.downshiftarr-real"
    real.write_text("# real\n", encoding="utf-8")
    real.chmod(0o755)
    telemetry_path = tmp_path / "telemetry" / "shim.json"
    index_path = tmp_path / "plex-version-index.json"
    input_file = "/media/movie-1080-sdr.mkv"
    fallback_file = "/media/movie-720-sdr.mkv"
    index_path.write_text(
        json.dumps(compact_v2_index(input_file, fallback_file, target_height=1080, fallback_height=720, rating_key="rk-1")),
        encoding="utf-8",
    )
    captured = {}

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "TELEMETRY_FILE", str(telemetry_path), raising=False)
    monkeypatch.setattr(shim, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(shim, "REQUIRE_STREAM_INDEX_COMPATIBILITY", False, raising=False)
    monkeypatch.setattr(shim, "resolve_real_transcoder_path", lambda: str(real))
    monkeypatch.setattr(
        shim,
        "plex_fetch_full_metadata",
        lambda rating_key: {"Media": [shim_media(input_file, 1080, "SDR"), shim_media(fallback_file, 720, "SDR")]},
    )
    monkeypatch.setattr(shim.sys, "argv", ["Plex Transcoder", "-i", input_file, "-f", "dash", "chunk"])
    monkeypatch.setattr(shim, "exec_real_transcoder", lambda real_path, args: captured.update({"real": real_path, "args": list(args)}))

    shim.main()

    assert captured["args"][1] == fallback_file
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert data["outcomes"]["waterfall_swap"]["count"] == 1
    assert "live_lookup_waterfall_swap" not in data["outcomes"]


def test_shim_can_disable_live_lookup_after_index_miss(monkeypatch, tmp_path):
    shim = load_shim()
    index_path = tmp_path / "plex-version-index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at_epoch": int(shim.time.time()),
                "items": [{"ratingKey": "other", "Media": [shim_media("/media/other.mkv", 1080, "SDR")]}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(shim, "VERSION_INDEX_FILE", str(index_path), raising=False)
    monkeypatch.setattr(shim, "ALLOW_LIVE_LOOKUP_ON_INDEX_MISS", False, raising=False)
    monkeypatch.setattr(
        shim,
        "plex_get_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("disabled live lookup should not call Plex")),
    )

    assert shim.plex_find_item_by_file("/media/movie-2160-hdr.mkv") is None


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
