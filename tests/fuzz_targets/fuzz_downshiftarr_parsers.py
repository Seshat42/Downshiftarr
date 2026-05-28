#!/usr/bin/env python3
"""Atheris target for Downshiftarr parser and policy helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

with atheris.instrument_imports():
    import Downshiftarr
    from tests.harness.fakes import attr


def TestOneInput(data: bytes) -> None:  # noqa: N802 - Atheris entrypoint convention
    provider = atheris.FuzzedDataProvider(data)
    text = provider.ConsumeUnicodeNoSurrogates(256)
    height = provider.ConsumeIntInRange(-5000, 10000)

    parsed = Downshiftarr.parse_resolution_hint(text)
    assert parsed is None or parsed > 0

    dynamic_range = Downshiftarr.classify_dynamic_range(text)
    assert dynamic_range in {"UNKNOWN", "SDR", "HDR", "DOLBY VISION"}

    high_quality = Downshiftarr.is_high_quality(height, text)
    assert isinstance(high_quality, bool)

    media_obj = attr(
        height=text,
        videoHeight=provider.ConsumeUnicodeNoSurrogates(32),
        videoDynamicRange=text,
        parts=[attr(streams=[attr(streamType=1, height=height, colorSpace=text)])],
    )
    Downshiftarr.media_height(media_obj)
    Downshiftarr.media_dynamic_range(media_obj)


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
