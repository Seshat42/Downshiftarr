from Downshiftarr import safe_int


class Unstringable:
    def __str__(self):
        raise RuntimeError("cannot convert to string")


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
    assert safe_int(Unstringable()) is None
