import Downshiftarr
from Downshiftarr import is_high_quality


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
