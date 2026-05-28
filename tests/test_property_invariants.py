from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

import Downshiftarr
from tests.harness.fakes import attr, media

pytestmark = [pytest.mark.property]


@given(st.one_of(st.none(), st.text(max_size=128), st.integers(min_value=-10000, max_value=10000)))
def test_resolution_hint_returns_none_or_positive_int(value):
    parsed = Downshiftarr.parse_resolution_hint(value)

    assert parsed is None or (isinstance(parsed, int) and parsed > 0)


@given(st.text(max_size=128))
def test_dynamic_range_classification_is_stable_and_bounded(value):
    first = Downshiftarr.classify_dynamic_range(value)
    second = Downshiftarr.classify_dynamic_range(f"  {value.lower()}  ")

    assert first in {"UNKNOWN", "SDR", "HDR", "DOLBY VISION"}
    assert second in {"UNKNOWN", "SDR", "HDR", "DOLBY VISION"}
    if value.strip():
        assert Downshiftarr.classify_dynamic_range(first) == first


@given(
    height=st.one_of(st.none(), st.integers(min_value=-100, max_value=5000)),
    dynamic_range=st.sampled_from(["", "UNKNOWN", "SDR", "HDR", "HLG", "DOVI", "Dolby Vision", "weird"]),
)
def test_high_quality_matches_height_and_dynamic_range_policy(height, dynamic_range):
    old_max = Downshiftarr.MAX_ALLOWED_HEIGHT
    Downshiftarr.MAX_ALLOWED_HEIGHT = 2000

    try:
        result = Downshiftarr.is_high_quality(height, dynamic_range)

        expected = bool(
            (height is not None and height >= 2000) or Downshiftarr.classify_dynamic_range(dynamic_range) not in {"SDR", "UNKNOWN"}
        )
        assert result is expected
    finally:
        Downshiftarr.MAX_ALLOWED_HEIGHT = old_max


@given(
    fallback_heights=st.lists(st.one_of(st.none(), st.sampled_from([360, 480, 720, 1080, 1440, 2160, 4320])), min_size=1, max_size=8),
    current_height=st.sampled_from([1080, 2160, 4320]),
)
def test_fallback_selection_never_selects_current_or_protected_media(fallback_heights, current_height):
    old_max = Downshiftarr.MAX_ALLOWED_HEIGHT
    old_prefer = Downshiftarr.PREFER_HEIGHTS
    old_sdr_only = Downshiftarr.FALLBACK_SDR_ONLY
    old_allow_hdr = Downshiftarr.ALLOW_HDR_FALLBACK
    Downshiftarr.MAX_ALLOWED_HEIGHT = 2000
    Downshiftarr.PREFER_HEIGHTS = (1080, 720, 480)
    Downshiftarr.FALLBACK_SDR_ONLY = True
    Downshiftarr.ALLOW_HDR_FALLBACK = False

    try:
        media_list = [media("current", current_height, "HDR", selected=True)]
        media_list.extend(media(f"candidate-{idx}", height, "SDR") for idx, height in enumerate(fallback_heights))
        item = attr(media=media_list)

        selected = Downshiftarr.pick_best_fallback_media_index(item, "current", current_height, "HDR")

        if selected is not None:
            chosen = media_list[selected]
            assert getattr(chosen, "id") != "current"
            assert Downshiftarr.media_height(chosen) is not None
            assert Downshiftarr.media_height(chosen) < Downshiftarr.MAX_ALLOWED_HEIGHT
            assert Downshiftarr.classify_dynamic_range(Downshiftarr.media_dynamic_range(chosen)) == "SDR"
    finally:
        Downshiftarr.MAX_ALLOWED_HEIGHT = old_max
        Downshiftarr.PREFER_HEIGHTS = old_prefer
        Downshiftarr.FALLBACK_SDR_ONLY = old_sdr_only
        Downshiftarr.ALLOW_HDR_FALLBACK = old_allow_hdr
