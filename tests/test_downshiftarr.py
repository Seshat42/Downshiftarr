import sys
import os
import unittest
from unittest.mock import patch

# Add parent directory to path so we can import Downshiftarr
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import Downshiftarr
from Downshiftarr import is_high_quality

class TestIsHighQuality(unittest.TestCase):

    @patch('Downshiftarr.MAX_ALLOWED_HEIGHT', 2000)
    def test_height_threshold(self):
        """Test height threshold detection"""
        # Exactly at threshold
        self.assertTrue(is_high_quality(2000, "SDR"))
        # Above threshold
        self.assertTrue(is_high_quality(2160, "SDR"))
        # Below threshold
        self.assertFalse(is_high_quality(1080, "SDR"))
        self.assertFalse(is_high_quality(1999, "SDR"))
        # No height
        self.assertFalse(is_high_quality(None, "SDR"))

    @patch('Downshiftarr.MAX_ALLOWED_HEIGHT', 2000)
    def test_dynamic_range(self):
        """Test dynamic range classification as high quality"""
        # Under height threshold, but HDR should still be high quality
        self.assertTrue(is_high_quality(1080, "HDR"))
        self.assertTrue(is_high_quality(1080, "DOVI"))
        self.assertTrue(is_high_quality(1080, "DOLBY VISION"))
        self.assertTrue(is_high_quality(1080, "HLG"))

        # Test case insensitivity (should be handled by classify_dynamic_range)
        self.assertTrue(is_high_quality(1080, "hdr10"))
        self.assertTrue(is_high_quality(1080, "dv"))

        # Non-high quality dynamic ranges
        self.assertFalse(is_high_quality(1080, "SDR"))
        self.assertFalse(is_high_quality(1080, "UNKNOWN"))
        self.assertFalse(is_high_quality(1080, ""))

    @patch('Downshiftarr.MAX_ALLOWED_HEIGHT', 2000)
    def test_combined_factors(self):
        """Test combined height and dynamic range"""
        # Both high quality
        self.assertTrue(is_high_quality(2160, "HDR"))
        # High quality height, low quality dyn range
        self.assertTrue(is_high_quality(2160, "SDR"))
        self.assertTrue(is_high_quality(2160, "UNKNOWN"))
        # Low quality height, high quality dyn range
        self.assertTrue(is_high_quality(1080, "HDR"))
        self.assertTrue(is_high_quality(1080, "DOLBY"))

    def test_custom_max_height(self):
        """Test with different MAX_ALLOWED_HEIGHT configurations"""
        with patch('Downshiftarr.MAX_ALLOWED_HEIGHT', 1080):
            # 1080 is now the threshold
            self.assertTrue(is_high_quality(1080, "SDR"))
            self.assertFalse(is_high_quality(720, "SDR"))

        with patch('Downshiftarr.MAX_ALLOWED_HEIGHT', 4000):
            # Higher threshold
            self.assertFalse(is_high_quality(2160, "SDR"))
            self.assertTrue(is_high_quality(4320, "SDR"))

if __name__ == '__main__':
    unittest.main()
