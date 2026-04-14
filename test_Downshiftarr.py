import pytest
from Downshiftarr import classify_dynamic_range

@pytest.mark.parametrize("dr, expected", [
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
    ("Some Random String", "HDR"), # Fallback
    ("SDR with HDR", "SDR"), # SDR takes precedence
    ("DOVI with SDR", "SDR"), # SDR takes precedence
    ("HDR with DOVI", "DOLBY VISION"), # DOVI takes precedence over HDR
])
def test_classify_dynamic_range(dr, expected):
    assert classify_dynamic_range(dr) == expected
