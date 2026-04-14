import unittest
from Downshiftarr import normalize_decision

class TestNormalizeDecision(unittest.TestCase):
    def test_normalize_decision_none(self):
        """Test that None returns an empty string."""
        self.assertEqual(normalize_decision(None), "")

    def test_normalize_decision_empty(self):
        """Test that an empty string returns an empty string."""
        self.assertEqual(normalize_decision(""), "")

    def test_normalize_decision_whitespace(self):
        """Test that a whitespace string returns an empty string."""
        self.assertEqual(normalize_decision("   "), "")

    def test_normalize_decision_normal(self):
        """Test that a normal string is converted to lowercase."""
        self.assertEqual(normalize_decision("transcode"), "transcode")

    def test_normalize_decision_mixed_case_with_spaces(self):
        """Test that a mixed case string with spaces is stripped and converted to lowercase."""
        self.assertEqual(normalize_decision("  DIRECT play  "), "direct play")

if __name__ == '__main__':
    unittest.main()
