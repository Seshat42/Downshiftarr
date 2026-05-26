import pytest
from Downshiftarr import parse_args, InputEvent

def test_parse_args_flag_mode_equals():
    argv = ["script.py", "--rating_key=123", "--client_machine_id=abc", "ignored_arg"]
    ev = parse_args(argv)
    assert ev.rating_key == "123"
    assert ev.machine_id == "abc"
    assert ev.username is None

def test_parse_args_flag_mode_spaces():
    argv = ["script.py", "--username", "testuser", "--videodecision", "transcode", "ignored_arg"]
    ev = parse_args(argv)
    assert ev.username == "testuser"
    assert ev.video_decision == "transcode"
    assert ev.machine_id is None

def test_parse_args_flag_mode_normalization():
    argv = ["script.py", "--Rating-Key", "456", "--Session-Id", "", "--Dynamic-Range", "hdr"]
    ev = parse_args(argv)
    assert ev.rating_key == "456"
    assert ev.session_id is None
    assert ev.video_dynamic_range == "hdr"

def test_parse_args_positional_mode_valid():
    # 8 arguments
    argv8 = ["script.py", "rk1", "mi1", "u1", "s1", "uid1", "rh1", "vd1"]
    ev8 = parse_args(argv8)
    assert ev8.rating_key == "rk1"
    assert ev8.machine_id == "mi1"
    assert ev8.username == "u1"
    assert ev8.session_id == "s1"
    assert ev8.user_id == "uid1"
    assert ev8.stream_video_resolution == "rh1"
    assert ev8.video_decision == "vd1"
    assert ev8.video_dynamic_range is None

    # 9 arguments
    argv9 = ["script.py", "rk2", "mi2", "u2", "s2", "uid2", "rh2", "vd2", "vdr2"]
    ev9 = parse_args(argv9)
    assert ev9.rating_key == "rk2"
    assert ev9.machine_id == "mi2"
    assert ev9.username == "u2"
    assert ev9.session_id == "s2"
    assert ev9.user_id == "uid2"
    assert ev9.stream_video_resolution == "rh2"
    assert ev9.video_decision == "vd2"
    assert ev9.video_dynamic_range == "vdr2"

def test_parse_args_positional_mode_insufficient_args():
    argv = ["script.py", "rk1", "mi1", "u1", "s1", "uid1", "rh1"]
    with pytest.raises(SystemExit):
        parse_args(argv)
