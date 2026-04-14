import pytest
from Downshiftarr import safe_int

class Unstringable:
    def __str__(self):
        raise RuntimeError("cannot convert to string")

def test_safe_int_none():
    assert safe_int(None) is None

def test_safe_int_valid_int():
    assert safe_int(42) == 42
    assert safe_int(0) == 0
    assert safe_int(-5) == -5

def test_safe_int_valid_str():
    assert safe_int("42") == 42
    assert safe_int("0") == 0
    assert safe_int("-5") == -5

def test_safe_int_invalid_str():
    assert safe_int("abc") is None
    assert safe_int("") is None

def test_safe_int_float():
    # int(str(42.5)) will attempt int("42.5") which raises ValueError, so it returns None
    assert safe_int(42.5) is None

def test_safe_int_exception():
    assert safe_int(Unstringable()) is None
