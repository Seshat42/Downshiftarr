import pytest

import Downshiftarr
from Downshiftarr import classify_dynamic_range, is_high_quality


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
