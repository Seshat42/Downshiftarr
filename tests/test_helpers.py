from Downshiftarr import env_bool, parse_resolution_hint, safe_int


class Unstringable:
    def __str__(self):
        raise RuntimeError("cannot convert to string")


def test_env_bool_missing_uses_default(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)

    assert not env_bool("MISSING_VAR")
    assert env_bool("MISSING_VAR", default=True)
    assert not env_bool("MISSING_VAR", default=False)


def test_env_bool_empty_or_whitespace_uses_default(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "")
    assert not env_bool("TEST_VAR")
    assert env_bool("TEST_VAR", default=True)

    monkeypatch.setenv("TEST_VAR", "   ")
    assert not env_bool("TEST_VAR")
    assert env_bool("TEST_VAR", default=True)


def test_env_bool_truthy_values(monkeypatch):
    for value in ("1", "true", "yes", "y", "on", "  True  ", "YES\n", "1 "):
        monkeypatch.setenv("TEST_VAR", value)
        assert env_bool("TEST_VAR")


def test_env_bool_falsy_values(monkeypatch):
    for value in ("0", "false", "no", "n", "off", "  False  ", "random", "2"):
        monkeypatch.setenv("TEST_VAR", value)
        assert not env_bool("TEST_VAR")
        assert not env_bool("TEST_VAR", default=True)


def test_safe_int_none():
    assert safe_int(None) is None


def test_safe_int_valid_ints():
    assert safe_int(42) == 42
    assert safe_int(0) == 0
    assert safe_int(-5) == -5


def test_safe_int_valid_strings():
    assert safe_int("42") == 42
    assert safe_int("0") == 0
    assert safe_int("-5") == -5


def test_safe_int_invalid_values():
    assert safe_int("abc") is None
    assert safe_int("") is None
    assert safe_int(42.5) is None
    assert safe_int("12.3") is None
    assert safe_int(Unstringable()) is None


def test_parse_resolution_hint_common_values():
    assert parse_resolution_hint("4k") == 2160
    assert parse_resolution_hint("UHD") == 2160
    assert parse_resolution_hint("2160p") == 2160
    assert parse_resolution_hint("1080p") == 1080
    assert parse_resolution_hint("1080i") == 1080
    assert parse_resolution_hint("720p") == 720
    assert parse_resolution_hint("576p") == 576
    assert parse_resolution_hint("480p") == 480


def test_parse_resolution_hint_numeric_values():
    assert parse_resolution_hint("2160") == 2160
    assert parse_resolution_hint("1080") == 1080
    assert parse_resolution_hint(2160) == 2160
    assert parse_resolution_hint("1440") == 1440
    assert parse_resolution_hint("360") == 360


def test_parse_resolution_hint_edge_cases():
    assert parse_resolution_hint(None) is None
    assert parse_resolution_hint("") is None
    assert parse_resolution_hint("   ") is None
    assert parse_resolution_hint("unknown") is None
    assert parse_resolution_hint("-10") is None


def test_parse_resolution_hint_whitespace_case_and_substrings():
    assert parse_resolution_hint("  4K  ") == 2160
    assert parse_resolution_hint("uhd") == 2160
    assert parse_resolution_hint("movie.1080p.x264") == 1080
    assert parse_resolution_hint("2160p.remux") == 2160
    assert parse_resolution_hint("4k movie") is None
