from Downshiftarr import normalize_decision


def test_normalize_decision_none():
    assert normalize_decision(None) == ""


def test_normalize_decision_empty():
    assert normalize_decision("") == ""


def test_normalize_decision_whitespace():
    assert normalize_decision("   ") == ""


def test_normalize_decision_normal():
    assert normalize_decision("transcode") == "transcode"


def test_normalize_decision_mixed_case_with_spaces():
    assert normalize_decision("  DIRECT play  ") == "direct play"
