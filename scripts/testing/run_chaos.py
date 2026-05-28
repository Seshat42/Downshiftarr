#!/usr/bin/env python3
"""Manual deterministic fake-service chaos runner for Downshiftarr."""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import Downshiftarr
from scripts.testing.hardening_catalog import redact_secrets
from tests.harness.client_profiles import video_capable_profiles
from tests.harness.fakes import FakeClient, FakePlexServer, attr, media

MANUAL_ENV = "DOWNSHIFTARR_HARDENING_MANUAL"


@dataclass(frozen=True)
class ChaosScenario:
    name: str
    description: str


SCENARIOS = (
    ChaosScenario("fake-service-faults", "Timeout-like Plex session lookup failures followed by recovery or fail-closed behavior."),
    ChaosScenario(
        "client-control-faults", "Remote-control play and seek failures stay bounded and use termination fallback only when needed."
    ),
    ChaosScenario("malformed-metadata", "Malformed Plex metadata returns safe UNKNOWN/None values rather than raising."),
)


class FlakyPlex(FakePlexServer):
    def __init__(self, fail_count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_count = fail_count
        self.calls = 0

    def sessions(self):
        self.calls += 1
        if self.calls <= self.fail_count:
            raise TimeoutError("synthetic Plex sessions timeout")
        return super().sessions()


def scenario_names() -> list[str]:
    return [scenario.name for scenario in SCENARIOS] + ["all"]


def print_scenarios() -> None:
    for scenario in SCENARIOS:
        print(f"{scenario.name}: {scenario.description}")


def _session():
    profile = video_capable_profiles()[0]
    player = profile.player
    player.viewOffset = 5000
    return attr(
        ratingKey="rk-chaos",
        sessionKey="session-chaos",
        session=attr(id="session-id"),
        user=attr(title="Downshiftarr Chaos"),
        player=player,
        viewOffset=5000,
        media=[media("current", 2160, "HDR", selected=True), media("fallback", 1080, "SDR")],
    )


def run_fake_service_faults(rng: random.Random, iterations: int) -> dict[str, int]:
    recovered = 0
    missed = 0
    for _ in range(iterations):
        fail_count = rng.choice([0, 1, 2])
        session = _session()
        plex = FlakyPlex(fail_count=fail_count, sessions=[session])
        previous_retries = Downshiftarr.SESSION_LOOKUP_RETRIES
        previous_delay = Downshiftarr.SESSION_LOOKUP_DELAY_S
        Downshiftarr.SESSION_LOOKUP_RETRIES = 3
        Downshiftarr.SESSION_LOOKUP_DELAY_S = 0
        try:
            context = Downshiftarr.find_session(plex, Downshiftarr.InputEvent(rating_key="rk-chaos", session_key="session-chaos"))
        finally:
            Downshiftarr.SESSION_LOOKUP_RETRIES = previous_retries
            Downshiftarr.SESSION_LOOKUP_DELAY_S = previous_delay
        if fail_count < 3:
            assert context is not None
            recovered += 1
        else:
            assert context is None
            missed += 1
    return {"iterations": iterations, "recovered": recovered, "missed": missed}


def run_client_control_faults(rng: random.Random, iterations: int) -> dict[str, int]:
    play_failures = 0
    seek_failures = 0
    for _ in range(iterations):
        profile = video_capable_profiles()[0]
        fail_play = rng.choice([True, False])
        fail_seek_attempts = rng.choice([0, 1, 2, 99])
        client = FakeClient(profile.machine_identifier, fail_play=fail_play, fail_seek_attempts=fail_seek_attempts)
        if fail_play:
            try:
                client.playMedia(attr(), offset=0, mediaIndex=1, partIndex=0)
            except RuntimeError:
                play_failures += 1
        else:
            client.playMedia(attr(), offset=0, mediaIndex=1, partIndex=0)
            try:
                client.seekTo(1000)
            except RuntimeError:
                seek_failures += 1
    return {"iterations": iterations, "play_failures": play_failures, "seek_failures": seek_failures}


def run_malformed_metadata(rng: random.Random, iterations: int) -> dict[str, int]:
    checked = 0
    malformed = [
        attr(parts=None),
        attr(parts=[attr(streams=None)]),
        attr(height="not-an-int", videoDynamicRange=""),
        attr(videoResolution="negative-resolution", parts=[attr(streams=[attr(streamType="video", height="not-an-int")])]),
    ]
    for _ in range(iterations):
        candidate = rng.choice(malformed)
        assert Downshiftarr.media_height(candidate) is None
        assert Downshiftarr.media_dynamic_range(candidate) in {"UNKNOWN", "HDR"}
        checked += 1
    return {"iterations": iterations, "checked": checked}


def run_scenario(name: str, seed: int, iterations: int) -> dict[str, int]:
    rng = random.Random(seed)
    if name == "fake-service-faults":
        return run_fake_service_faults(rng, iterations)
    if name == "client-control-faults":
        return run_client_control_faults(rng, iterations)
    if name == "malformed-metadata":
        return run_malformed_metadata(rng, iterations)
    if name == "all":
        total = {"iterations": 0}
        for scenario in SCENARIOS:
            result = run_scenario(scenario.name, seed, iterations)
            total["iterations"] += result.get("iterations", 0)
        return total
    raise KeyError(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-scenarios", action="store_true", help="List chaos scenarios and exit.")
    parser.add_argument("--scenario", choices=scenario_names(), default="fake-service-faults")
    parser.add_argument("--seed", type=int, default=515151)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--run", action="store_true", help="Actually run the selected scenario.")
    args = parser.parse_args(argv)

    if args.list_scenarios:
        print_scenarios()
        return 0

    print(
        redact_secrets(
            f"Prepared chaos scenario={args.scenario} seed={args.seed} iterations={max(1, args.iterations)}. "
            f"Set {MANUAL_ENV}=1 and pass --run to execute."
        )
    )
    if not args.run:
        return 0
    if os.environ.get(MANUAL_ENV) != "1":
        print(f"Refusing to run chaos testing without {MANUAL_ENV}=1.", file=sys.stderr)
        return 2

    result = run_scenario(args.scenario, args.seed, max(1, args.iterations))
    print(redact_secrets(f"Chaos scenario passed: {result}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
