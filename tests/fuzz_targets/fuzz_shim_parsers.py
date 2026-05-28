#!/usr/bin/env python3
"""Atheris target for the Plex Transcoder shim parser and rewrite helpers."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import atheris


def load_shim():
    path = Path(__file__).resolve().parents[2] / "Plex Transcoder"
    loader = importlib.machinery.SourceFileLoader("plex_transcoder_shim_atheris", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


with atheris.instrument_imports():
    SHIM = load_shim()


def TestOneInput(data: bytes) -> None:  # noqa: N802 - Atheris entrypoint convention
    provider = atheris.FuzzedDataProvider(data)
    args = [provider.ConsumeUnicodeNoSurrogates(48) for _ in range(provider.ConsumeIntInRange(0, 24))]
    filter_graph = provider.ConsumeUnicodeNoSurrogates(512)

    primary, input_index = SHIM.find_primary_input(args)
    assert primary is None or isinstance(primary, str)
    assert input_index == -1 or 0 <= input_index < len(args)

    max_stream = SHIM.required_max_input_stream_index(args)
    assert max_stream is None or max_stream >= 0

    rewritten_filter, _ = SHIM._rewrite_filter_graph(filter_graph)
    rewritten_again, _ = SHIM._rewrite_filter_graph(rewritten_filter)
    assert rewritten_again == rewritten_filter

    rewritten_args = SHIM.rewrite_args_for_performance(list(args), input_index, swapped_to_sdr=True)
    assert isinstance(rewritten_args, list)

    media = {
        "height": provider.ConsumeUnicodeNoSurrogates(16),
        "videoResolution": provider.ConsumeUnicodeNoSurrogates(16),
        "videoDynamicRange": provider.ConsumeUnicodeNoSurrogates(32),
        "Part": [{"file": provider.ConsumeUnicodeNoSurrogates(64), "Stream": [{"streamType": 1, "index": provider.ConsumeInt(8)}]}],
    }
    SHIM.build_media_info(media)


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
