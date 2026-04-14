import pytest
from unittest.mock import MagicMock
import sys

# Mock dependencies before importing Downshiftarr
sys.modules['requests'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['plexapi'] = MagicMock()
sys.modules['plexapi.server'] = MagicMock()
sys.modules['plexapi.client'] = MagicMock()

from Downshiftarr import parse_resolution_hint, safe_int

def test_safe_int():
    assert safe_int(123) == 123
    assert safe_int("456") == 456
    assert safe_int(None) is None
    assert safe_int("abc") is None
    assert safe_int("") is None
    # safe_int uses int(str(x)) which for "12.3" would raise ValueError and return None
    assert safe_int(12.3) is None
    assert safe_int("12.3") is None

def test_parse_resolution_hint():
    # Happy paths
    assert parse_resolution_hint("4k") == 2160
    assert parse_resolution_hint("UHD") == 2160
    assert parse_resolution_hint("2160p") == 2160
    assert parse_resolution_hint("1080p") == 1080
    assert parse_resolution_hint("1080i") == 1080
    assert parse_resolution_hint("720p") == 720
    assert parse_resolution_hint("576p") == 576
    assert parse_resolution_hint("480p") == 480

    # Numeric strings
    assert parse_resolution_hint("2160") == 2160
    assert parse_resolution_hint("1080") == 1080
    assert parse_resolution_hint(2160) == 2160

    # Edge cases
    assert parse_resolution_hint(None) is None
    assert parse_resolution_hint("") is None
    assert parse_resolution_hint("   ") is None
    assert parse_resolution_hint("unknown") is None

    # Case sensitivity and whitespace
    assert parse_resolution_hint("  4K  ") == 2160
    assert parse_resolution_hint("uhd") == 2160

    # Substring matching (demonstrating current behavior)
    assert parse_resolution_hint("movie.1080p.x264") == 1080
    assert parse_resolution_hint("2160p.remux") == 2160
    # Note: "4k" and "uhd" only match if they are the entire (stripped) string
    assert parse_resolution_hint("4k movie") is None

    # Other numbers
    assert parse_resolution_hint("1440") == 1440
    assert parse_resolution_hint("360") == 360
    assert parse_resolution_hint("-10") is None # int(s) > 0 check
