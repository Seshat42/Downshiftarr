import pytest

import Downshiftarr
from Downshiftarr import classify_dynamic_range, is_high_quality, should_waterfall_continued_transcode


@pytest.mark.parametrize(
    ("dynamic_range", "expected"),
    [
        ("", "UNKNOWN"),
        (None, "UNKNOWN"),
        ("   ", "UNKNOWN"),
        ("UNKNOWN", "UNKNOWN"),
        ("unknown", "UNKNOWN"),
        ("NONE", "UNKNOWN"),
        ("none", "UNKNOWN"),
        ("SDR", "SDR"),
        ("sdr", "SDR"),
        ("  SDR  ", "SDR"),
        ("Standard Dynamic Range SDR", "SDR"),
        ("DOVI", "DOLBY VISION"),
        ("dovi", "DOLBY VISION"),
        ("DOLBY", "DOLBY VISION"),
        ("dolby", "DOLBY VISION"),
        ("VISION", "DOLBY VISION"),
        ("vision", "DOLBY VISION"),
        ("DV", "DOLBY VISION"),
        ("dv", "DOLBY VISION"),
        ("DOLBY VISION", "DOLBY VISION"),
        ("dovi profile 8", "DOLBY VISION"),
        ("HDR", "HDR"),
        ("hdr", "HDR"),
        ("HLG", "HDR"),
        ("hlg", "HDR"),
        ("hdr10", "HDR"),
        ("HDR10+", "HDR"),
        ("hlg10", "HDR"),
        ("Some Random String", "HDR"),
        ("SDR with HDR", "SDR"),
        ("DOVI with SDR", "SDR"),
        ("HDR with DOVI", "DOLBY VISION"),
    ],
)
def test_classify_dynamic_range(dynamic_range, expected):
    assert classify_dynamic_range(dynamic_range) == expected


def test_is_high_quality_by_height_threshold(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 2000)

    assert is_high_quality(2000, "SDR")
    assert is_high_quality(2160, "SDR")
    assert not is_high_quality(1080, "SDR")
    assert not is_high_quality(1999, "SDR")
    assert not is_high_quality(None, "SDR")


def test_default_protected_height_is_anything_above_1080():
    assert Downshiftarr.PROTECTED_SOURCE_MIN_HEIGHT == 1081
    assert not Downshiftarr.is_protected_source_height(1080)
    assert Downshiftarr.is_protected_source_height(1081)
    assert Downshiftarr.is_protected_source_height(1440)
    assert Downshiftarr.is_protected_source_height(2160)


def test_1080_hdr_waterfalls_by_default_without_hard_protection(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "PROTECTED_SOURCE_MIN_HEIGHT", 1081)
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 1081)
    monkeypatch.setattr(Downshiftarr, "HARD_PROTECT_1080_HDR", False, raising=False)

    assert not Downshiftarr.is_hard_protected_source(1080, "HDR")
    assert should_waterfall_continued_transcode(1080, "HDR")


def test_1080_hdr_can_be_hard_protected_by_config(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "HARD_PROTECT_1080_HDR", True, raising=False)

    assert Downshiftarr.is_hard_protected_source(1080, "HDR")


def test_1080_remux_like_bitrate_is_configurable(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "REMUX_1080_MIN_BITRATE_KBPS", 25_000, raising=False)

    assert Downshiftarr.is_1080_remux_like(1080, "", 25_000)
    assert Downshiftarr.is_1080_remux_like(1080, "/media/movie-remux.mkv", None)
    assert not Downshiftarr.is_1080_remux_like(1080, "", 12_000)
    assert not Downshiftarr.is_1080_remux_like(720, "", 30_000)


def test_is_high_quality_by_dynamic_range(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 2000)

    assert is_high_quality(1080, "HDR")
    assert is_high_quality(1080, "DOVI")
    assert is_high_quality(1080, "DOLBY VISION")
    assert is_high_quality(1080, "HLG")
    assert is_high_quality(1080, "hdr10")
    assert is_high_quality(1080, "dv")

    assert not is_high_quality(1080, "SDR")
    assert not is_high_quality(1080, "UNKNOWN")
    assert not is_high_quality(1080, "")


def test_is_high_quality_combines_height_and_dynamic_range(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 2000)

    assert is_high_quality(2160, "HDR")
    assert is_high_quality(2160, "SDR")
    assert is_high_quality(2160, "UNKNOWN")
    assert is_high_quality(1080, "HDR")
    assert is_high_quality(1080, "DOLBY")


def test_is_high_quality_respects_configured_max_height(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 1080)
    assert is_high_quality(1080, "SDR")
    assert not is_high_quality(720, "SDR")

    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 4000)
    assert not is_high_quality(2160, "SDR")
    assert is_high_quality(4320, "SDR")
