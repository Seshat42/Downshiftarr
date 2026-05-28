from Downshiftarr import media_height


class MockObj:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_media_height_reads_height_attributes():
    assert media_height(MockObj(height=1080)) == 1080
    assert media_height(MockObj(height="720")) == 720
    assert media_height(MockObj(videoHeight=2160)) == 2160


def test_media_height_reads_resolution_hints():
    assert media_height(MockObj(videoResolution="4k")) == 2160
    assert media_height(MockObj(resolution="1080")) == 1080


def test_media_height_falls_back_to_video_stream_height():
    stream_video = MockObj(streamType=1, height=1080)
    stream_audio = MockObj(streamType=2)
    part = MockObj(streams=[stream_audio, stream_video])

    assert media_height(MockObj(parts=[part])) == 1080


def test_media_height_returns_none_without_valid_video_height():
    assert media_height(MockObj()) is None
    assert media_height(None) is None
    assert media_height("not an object") is None

    stream_audio = MockObj(streamType=2, height=1080)
    stream_video_no_height = MockObj(streamType=1)
    part = MockObj(streams=[stream_audio, stream_video_no_height])

    assert media_height(MockObj(parts=[part])) is None
