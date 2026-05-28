#!/usr/bin/env python3
"""Manual seeded monkey-test runner for fake Plex/Tautulli/client events."""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import Downshiftarr
from scripts.testing.hardening_catalog import redact_secrets
from tests.harness.client_profiles import CLIENT_PROFILES, ClientProfile, video_capable_profiles
from tests.harness.fakes import FakeClient, FakePlexServer, attr, media

MANUAL_ENV = "DOWNSHIFTARR_HARDENING_MANUAL"


@dataclass(frozen=True)
class MonkeyScenario:
    name: str
    description: str


SCENARIOS = (
    MonkeyScenario("client-event-matrix", "Randomized protected/non-protected fake sessions across all video-capable Plex clients."),
    MonkeyScenario("accessory-noop", "Accessory/non-video client families must not be unsafe-enforced without a video transcode session."),
    MonkeyScenario("fallback-selection", "Randomized media version lists must never choose protected/current media as fallback."),
)


def scenario_names() -> list[str]:
    return [scenario.name for scenario in SCENARIOS] + ["all"]


def print_scenarios() -> None:
    for scenario in SCENARIOS:
        print(f"{scenario.name}: {scenario.description}")


def _protected_session(profile: ClientProfile, height: int, dynamic_range: str) -> Any:
    player = profile.player
    player.viewOffset = 1000
    return attr(
        ratingKey="rk-monkey",
        sessionKey="session-monkey",
        session=attr(id="session-id"),
        user=attr(title="Downshiftarr Monkey"),
        player=player,
        viewOffset=1000,
        media=[
            media("current", height, dynamic_range, selected=True),
            media("fallback-1080-sdr", 1080, "SDR"),
            media("fallback-720-sdr", 720, "SDR"),
        ],
    )


def run_client_event_matrix(rng: random.Random, iterations: int) -> dict[str, int]:
    profiles = video_capable_profiles()
    downshifted = 0
    ignored = 0
    for _ in range(iterations):
        profile = rng.choice(profiles)
        protected = rng.choice([True, False])
        session = _protected_session(profile, 2160 if protected else rng.choice([480, 720, 1080]), "HDR" if protected else "SDR")
        client = FakeClient(machine_identifier=profile.machine_identifier)
        plex = FakePlexServer(sessions=[session], clients=[client])
        event = Downshiftarr.InputEvent(rating_key="rk-monkey", session_key="session-monkey", machine_id=profile.machine_identifier)
        context = Downshiftarr.find_session(plex, event)
        assert context is not None
        found_client, _ = Downshiftarr.find_client(plex, context, event.machine_id)
        assert found_client is client
        current_id, current_height, current_dr = Downshiftarr.current_media_identity(session)
        if not Downshiftarr.is_high_quality(current_height, current_dr):
            ignored += 1
            continue
        fallback = Downshiftarr.pick_best_fallback_media_index(session, current_id, current_height, current_dr)
        if protected:
            assert fallback in (1, 2)
            downshifted += 1
    return {"iterations": iterations, "downshifted": downshifted, "ignored": ignored}


def run_accessory_noop(rng: random.Random, iterations: int) -> dict[str, int]:
    profiles = tuple(profile for profile in CLIENT_PROFILES if not profile.video_capable)
    checked = 0
    for _ in range(iterations):
        profile = rng.choice(profiles)
        decision = rng.choice(["direct play", "direct stream", "copy"])
        assert not Downshiftarr.is_video_transcoding(decision)
        assert profile.video_capable is False
        checked += 1
    return {"iterations": iterations, "checked": checked}


def run_fallback_selection(rng: random.Random, iterations: int) -> dict[str, int]:
    selected = 0
    for _ in range(iterations):
        current_height = rng.choice([1080, 1440, 2160, 4320])
        variants = [media("current", current_height, rng.choice(["HDR", "DOLBY VISION"]), selected=True)]
        for idx in range(rng.randint(1, 6)):
            variants.append(
                media(f"candidate-{idx}", rng.choice([360, 480, 720, 1080, 1440, 2160, None]), rng.choice(["SDR", "HDR", "UNKNOWN"]))
            )
        item = attr(media=variants)
        fallback = Downshiftarr.pick_best_fallback_media_index(item, "current", current_height, "HDR")
        if fallback is not None:
            candidate = variants[fallback]
            assert getattr(candidate, "id") != "current"
            assert Downshiftarr.media_height(candidate) < Downshiftarr.MAX_ALLOWED_HEIGHT
            selected += 1
    return {"iterations": iterations, "selected": selected}


def run_scenario(name: str, seed: int, iterations: int) -> dict[str, int]:
    rng = random.Random(seed)
    if name == "client-event-matrix":
        return run_client_event_matrix(rng, iterations)
    if name == "accessory-noop":
        return run_accessory_noop(rng, iterations)
    if name == "fallback-selection":
        return run_fallback_selection(rng, iterations)
    if name == "all":
        total = {"iterations": 0}
        for scenario in SCENARIOS:
            result = run_scenario(scenario.name, seed, iterations)
            total["iterations"] += result.get("iterations", 0)
        return total
    raise KeyError(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-scenarios", action="store_true", help="List monkey scenarios and exit.")
    parser.add_argument("--scenario", choices=scenario_names(), default="client-event-matrix")
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--iterations", type=int, default=250)
    parser.add_argument("--run", action="store_true", help="Actually run the selected scenario.")
    args = parser.parse_args(argv)

    if args.list_scenarios:
        print_scenarios()
        return 0

    prepared = (
        f"Prepared monkey scenario={args.scenario} seed={args.seed} iterations={max(1, args.iterations)}. "
        f"Set {MANUAL_ENV}=1 and pass --run to execute."
    )
    print(redact_secrets(prepared))
    if not args.run:
        return 0
    if os.environ.get(MANUAL_ENV) != "1":
        print(f"Refusing to run monkey testing without {MANUAL_ENV}=1.", file=sys.stderr)
        return 2

    result = run_scenario(args.scenario, args.seed, max(1, args.iterations))
    print(redact_secrets(f"Monkey scenario passed: {result}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
