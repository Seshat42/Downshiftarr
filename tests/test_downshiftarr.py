import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Downshiftarr import media_dynamic_range


class MockObj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_media_dynamic_range_explicit_attrs():
    # videoDynamicRange
    obj = MockObj(videoDynamicRange="hdr")
    assert media_dynamic_range(obj) == "HDR"

    # dynamicRange
    obj = MockObj(dynamicRange="sdr")
    assert media_dynamic_range(obj) == "SDR"

    # videoDynamicRangeType
    obj = MockObj(videoDynamicRangeType="Dolby Vision")
    assert media_dynamic_range(obj) == "DOLBY VISION"


def test_media_dynamic_range_stream_inspection_dolby_vision():
    # DOVIPresent
    stream = MockObj(streamType=1, DOVIPresent="1")
    part = MockObj(streams=[stream])
    obj = MockObj(parts=[part])
    assert media_dynamic_range(obj) == "DOLBY VISION"

    # dolbyVision
    stream = MockObj(streamType=1, dolbyVision="true")
    part = MockObj(streams=[stream])
    obj = MockObj(parts=[part])
    assert media_dynamic_range(obj) == "DOLBY VISION"


def test_media_dynamic_range_stream_inspection_hdr():
    # colorSpace
    stream = MockObj(streamType=1, colorSpace="bt2020nc (HDR)")
    part = MockObj(streams=[stream])
    obj = MockObj(parts=[part])
    assert media_dynamic_range(obj) == "HDR"


def test_media_dynamic_range_ignore_non_video_streams():
    # Stream type 2 (audio) has dolbyVision, should be ignored
    stream = MockObj(streamType=2, dolbyVision="true")
    part = MockObj(streams=[stream])
    obj = MockObj(parts=[part])
    assert media_dynamic_range(obj) == "UNKNOWN"


def test_media_dynamic_range_unknown():
    obj = MockObj()
    assert media_dynamic_range(obj) == "UNKNOWN"


def test_media_dynamic_range_exception():
    # Raise exception during stream access
    class FaultyObj:
        @property
        def parts(self):
            raise ValueError("Some error")

    assert media_dynamic_range(FaultyObj()) == "UNKNOWN"


def test_media_dynamic_range_stream_inspection_no_hdr_dovi_found():
    stream = MockObj(
        streamType=1,
        DOVIPresent=None,
        doviPresent=None,
        dolbyVision=None,
        colorSpace="sdr",
        colorTransfer="sdr",
        colorPrimaries="sdr",
        hdr="sdr",
    )
    part = MockObj(streams=[stream])
    obj = MockObj(parts=[part])
    assert media_dynamic_range(obj) == "UNKNOWN"


def test_media_dynamic_range_stream_inspection_invalid_part_and_streams():
    # parts is None
    obj = MockObj(parts=None)
    assert media_dynamic_range(obj) == "UNKNOWN"

    # streams is None
    part = MockObj(streams=None)
    obj = MockObj(parts=[part])
    assert media_dynamic_range(obj) == "UNKNOWN"
