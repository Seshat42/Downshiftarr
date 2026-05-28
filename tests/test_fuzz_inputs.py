from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

import Downshiftarr
from tests.harness.shim_loader import load_shim

pytestmark = [pytest.mark.fuzz]


@given(st.text(max_size=512))
def test_downshiftarr_string_helpers_survive_hostile_text(value):
    Downshiftarr.parse_resolution_hint(value)
    decision = Downshiftarr.normalize_decision(value)
    dynamic_range = Downshiftarr.classify_dynamic_range(value)

    assert isinstance(decision, str)
    assert dynamic_range in {"UNKNOWN", "SDR", "HDR", "DOLBY VISION"}


@given(st.lists(st.text(max_size=64), max_size=40))
def test_shim_arg_parsers_survive_hostile_vectors(args):
    shim = load_shim("plex_transcoder_shim_fuzz_args")

    path, input_index = shim.find_primary_input(args)
    max_stream = shim.required_max_input_stream_index(args)
    rewritten = shim.rewrite_args_for_performance(list(args), input_index, swapped_to_sdr=True)

    assert path is None or isinstance(path, str)
    assert input_index == -1 or 0 <= input_index < len(args)
    assert max_stream is None or max_stream >= 0
    assert isinstance(rewritten, list)


@given(st.text(max_size=512))
def test_shim_filter_rewrite_is_idempotent_for_fuzzed_filters(filter_graph):
    shim = load_shim("plex_transcoder_shim_fuzz_filters")

    once, _ = shim._rewrite_filter_graph(filter_graph)
    twice, _ = shim._rewrite_filter_graph(once)

    assert isinstance(once, str)
    assert twice == once
