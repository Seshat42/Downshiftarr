import unittest
import sys
import os

# Add the parent directory to the python path so we can import Downshiftarr
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Downshiftarr import media_height

class MockObj:
    """A simple mock object to simulate Plex models with dynamic attributes."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class TestMediaHeight(unittest.TestCase):

    def test_height_attribute(self):
        # Test 'height'
        media = MockObj(height=1080)
        self.assertEqual(media_height(media), 1080)

        # Test 'height' as string
        media = MockObj(height="720")
        self.assertEqual(media_height(media), 720)

    def test_video_height_attribute(self):
        # Test 'videoHeight'
        media = MockObj(videoHeight=2160)
        self.assertEqual(media_height(media), 2160)

    def test_resolution_hint(self):
        # Test 'videoResolution'
        media = MockObj(videoResolution="4k")
        self.assertEqual(media_height(media), 2160)

        # Test 'resolution'
        media = MockObj(resolution="1080")
        self.assertEqual(media_height(media), 1080)

    def test_stream_inspection(self):
        # Test fallback to parts/streams
        stream_video = MockObj(streamType=1, height=1080)
        stream_audio = MockObj(streamType=2)
        part = MockObj(streams=[stream_audio, stream_video])
        media = MockObj(parts=[part])

        self.assertEqual(media_height(media), 1080)

        # Test when no video stream has height
        stream_video_no_height = MockObj(streamType=1)
        part_no_height = MockObj(streams=[stream_audio, stream_video_no_height])
        media_no_height = MockObj(parts=[part_no_height])

        self.assertIsNone(media_height(media_no_height))

    def test_none_and_missing_attributes(self):
        media = MockObj()
        self.assertIsNone(media_height(media))

        # Test with invalid types
        self.assertIsNone(media_height(None))
        self.assertIsNone(media_height("not an object"))

if __name__ == '__main__':
    unittest.main()
