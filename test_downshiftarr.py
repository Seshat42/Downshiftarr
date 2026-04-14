import os
import pytest
from Downshiftarr import env_bool

def test_env_bool_missing_default(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    assert env_bool("MISSING_VAR") is False
    assert env_bool("MISSING_VAR", default=True) is True
    assert env_bool("MISSING_VAR", default=False) is False

def test_env_bool_empty(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "")
    assert env_bool("TEST_VAR") is False
    assert env_bool("TEST_VAR", default=True) is True

    monkeypatch.setenv("TEST_VAR", "   ")
    assert env_bool("TEST_VAR") is False
    assert env_bool("TEST_VAR", default=True) is True

def test_env_bool_truthy(monkeypatch):
    truthy_values = ["1", "true", "yes", "y", "on", "  True  ", "YES\n", "1 "]
    for val in truthy_values:
        monkeypatch.setenv("TEST_VAR", val)
        assert env_bool("TEST_VAR") is True

def test_env_bool_falsy(monkeypatch):
    falsy_values = ["0", "false", "no", "n", "off", "  False  ", "random", "2"]
    for val in falsy_values:
        monkeypatch.setenv("TEST_VAR", val)
        assert env_bool("TEST_VAR") is False
        assert env_bool("TEST_VAR", default=True) is False
