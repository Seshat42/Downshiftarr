import pytest

import Downshiftarr
from Downshiftarr import InputEvent, find_client, find_session, pick_best_fallback_media_index, plex_terminate_session
from tests.harness.client_profiles import CLIENT_PROFILES, ClientProfile, video_capable_profiles
from tests.harness.fakes import FakeClient, FakePlexServer, attr, media

pytestmark = [pytest.mark.simulated]


def protected_session(
    *, profile: ClientProfile | None = None, machine_identifier: str | None = "client-plex-web-chrome", view_offset: int = 1234
):
    player = profile.player if profile else attr(title="Plex Web Chrome", product="Plex Web", platform="Chrome")
    player.viewOffset = view_offset
    if machine_identifier:
        player.machineIdentifier = machine_identifier
        player.clientIdentifier = machine_identifier
    return attr(
        ratingKey="rk-1",
        sessionKey="session-key",
        session=attr(id="session-id"),
        user=attr(title="Downshiftarr Test User"),
        player=player,
        viewOffset=view_offset,
        media=[
            media("current-4k-hdr", 2160, "HDR", selected=True),
            media("fallback-1080-sdr", 1080, "SDR"),
        ],
    )


def run_main_with_fake_plex(
    monkeypatch,
    plex,
    *,
    profile: ClientProfile | None = None,
    video_decision: str = "transcode",
    dynamic_range: str = "HDR",
):
    terminations = []
    monkeypatch.setattr(Downshiftarr, "connect_plex", lambda: plex)
    monkeypatch.setattr(Downshiftarr, "terminate_best_effort", lambda plex, ev, ctx, message: terminations.append(message) or True)
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_RETRIES", 1)
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_DELAY_S", 0)
    monkeypatch.setattr(Downshiftarr, "SEEK_DELAY_S", 0)
    monkeypatch.setattr(Downshiftarr, "SEEK_RETRY_DELAY_S", 0)
    monkeypatch.setattr(Downshiftarr, "SEEK_RETRIES", 2)
    monkeypatch.setattr(Downshiftarr, "KILL_ON_CLIENT_NOT_FOUND", True)
    monkeypatch.setattr(Downshiftarr, "KILL_ON_SWITCH_FAIL", True)

    code = Downshiftarr.main(
        [
            "Downshiftarr.py",
            "--rating-key=rk-1",
            "--session-key=session-key",
            "--session-id=session-id",
            "--username=Downshiftarr Test User",
            f"--machine-id={profile.machine_identifier if profile else 'client-plex-web-chrome'}",
            f"--video-decision={video_decision}",
            f"--video-dynamic-range={dynamic_range}",
        ]
    )
    return code, terminations


@pytest.mark.parametrize("profile", CLIENT_PROFILES, ids=lambda p: p.name)
def test_client_profile_matrix_matches_session_and_client(profile, monkeypatch):
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_RETRIES", 1)

    session = attr(
        ratingKey="rk-1",
        sessionKey="session-key",
        session=attr(id="session-id"),
        user=attr(title="Downshiftarr Test User"),
        player=profile.player,
        viewOffset=1234,
    )
    client = FakeClient(machine_identifier=profile.machine_identifier)
    plex = FakePlexServer(sessions=[session], clients=[client])
    event = InputEvent(rating_key="rk-1", session_key="session-key", machine_id=profile.machine_identifier)

    context = find_session(plex, event)
    found_client, identifier = find_client(plex, context, event.machine_id)

    assert context.session_id == "session-id"
    assert context.machine_id == profile.machine_identifier
    assert found_client is client
    assert identifier == profile.machine_identifier


def test_fallback_selection_prefers_1080_sdr_for_4k_hdr(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "MAX_ALLOWED_HEIGHT", 2000)
    monkeypatch.setattr(Downshiftarr, "PREFER_HEIGHTS", (1080, 720, 480))
    monkeypatch.setattr(Downshiftarr, "FALLBACK_SDR_ONLY", True)

    item = attr(
        media=[
            media("current-4k-hdr", 2160, "HDR", selected=True),
            media("fallback-720-sdr", 720, "SDR"),
            media("fallback-1080-sdr", 1080, "SDR"),
            media("fallback-1080-hdr", 1080, "HDR"),
        ]
    )

    assert pick_best_fallback_media_index(item, "current-4k-hdr", 2160, "HDR") == 2


def test_plex_terminate_session_uses_headers_not_token_query(monkeypatch):
    captured = {}

    class FakeHttp:
        def get(self, url, params, headers, timeout):
            captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
            return attr(status_code=200)

    monkeypatch.setattr(Downshiftarr, "PLEX_URL", "http://127.0.0.1:32400")
    monkeypatch.setattr(Downshiftarr, "PLEX_EFFECTIVE_TOKEN", "secret-token")
    monkeypatch.setattr(Downshiftarr, "PLEX_HTTP", FakeHttp())

    assert plex_terminate_session(None, "session-id", "test reason")
    assert captured["url"] == "http://127.0.0.1:32400/status/sessions/terminate"
    assert captured["params"] == {"sessionId": "session-id", "reason": "test reason"}
    assert captured["headers"] == {"X-Plex-Token": "secret-token"}


def test_missing_controllable_client_terminates_fail_closed(monkeypatch):
    session = protected_session(machine_identifier=None)
    plex = FakePlexServer(sessions=[session], clients=[])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex)

    assert code == 0
    assert terminations == [Downshiftarr.KILL_MESSAGE_CLIENT_NOT_FOUND]


def test_remote_control_failure_terminates_fail_closed(monkeypatch):
    session = protected_session(machine_identifier="client-plex-web")
    client = FakeClient(machine_identifier="client-plex-web", fail_play=True)
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex)

    assert code == 0
    assert terminations == [Downshiftarr.KILL_MESSAGE_SWITCH_FAIL]
    assert client.play_calls == []


def test_seek_failure_does_not_override_successful_play_command(monkeypatch):
    session = protected_session(machine_identifier="client-plex-web", view_offset=5000)
    client = FakeClient(machine_identifier="client-plex-web", fail_seek_attempts=99)
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex)

    assert code == 0
    assert terminations == []
    assert client.play_calls == [{"item": session, "offset": 5000, "mediaIndex": 1, "partIndex": 0}]
    assert client.seek_calls == [5000, 5000]


@pytest.mark.parametrize("profile", video_capable_profiles(), ids=lambda p: p.name)
def test_every_video_client_profile_downshifts_protected_transcode(profile, monkeypatch):
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier, view_offset=2222)
    client = FakeClient(machine_identifier=profile.machine_identifier)
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex, profile=profile)

    assert code == 0
    assert terminations == []
    assert client.play_calls == [{"item": session, "offset": 2222, "mediaIndex": 1, "partIndex": 0}]
    assert client.seek_calls == [2222]


@pytest.mark.parametrize(
    ("current_height", "expected_index"),
    [
        (1080, 1),
        (720, 2),
        (480, 3),
    ],
)
def test_continued_transcode_waterfalls_to_next_lower_version_by_default(monkeypatch, current_height, expected_index):
    media_rows = [
        media("fallback-720-sdr", 720, "SDR", selected=current_height == 720),
        media("fallback-480-sdr", 480, "SDR", selected=current_height == 480),
        media("fallback-360-sdr", 360, "SDR", selected=current_height == 360),
    ]
    media_rows.insert(0, media("fallback-1080-sdr", 1080, "SDR", selected=current_height == 1080))
    session = protected_session(machine_identifier="client-plex-web", view_offset=3333)
    session.media = media_rows
    client = FakeClient(machine_identifier="client-plex-web")
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex)

    assert code == 0
    assert terminations == []
    assert client.play_calls == [{"item": session, "offset": 3333, "mediaIndex": expected_index, "partIndex": 0}]
    assert client.seek_calls == [3333]


def test_continued_transcode_at_lowest_version_passes_without_termination(monkeypatch):
    session = protected_session(machine_identifier="client-plex-web")
    session.media = [media("fallback-360-sdr", 360, "SDR", selected=True)]
    client = FakeClient(machine_identifier="client-plex-web")
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex)

    assert code == 0
    assert terminations == []
    assert client.play_calls == []


@pytest.mark.parametrize("decision", ["direct play", "direct stream"])
@pytest.mark.parametrize("profile", video_capable_profiles(), ids=lambda p: p.name)
def test_every_video_client_profile_ignores_non_transcode_decisions(profile, decision, monkeypatch):
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
    client = FakeClient(machine_identifier=profile.machine_identifier)
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex, profile=profile, video_decision=decision)

    assert code == 0
    assert terminations == []
    assert client.play_calls == []


@pytest.mark.parametrize("profile", video_capable_profiles(), ids=lambda p: p.name)
def test_every_video_client_profile_no_fallback_terminates_fail_closed(profile, monkeypatch):
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
    session.media = [media("current-4k-hdr", 2160, "HDR", selected=True)]
    plex = FakePlexServer(sessions=[session], clients=[FakeClient(machine_identifier=profile.machine_identifier)])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex, profile=profile)

    assert code == 0
    assert terminations == [Downshiftarr.KILL_MESSAGE_NO_FALLBACK_MEDIA]


@pytest.mark.parametrize("profile", video_capable_profiles(), ids=lambda p: p.name)
def test_every_video_client_profile_missing_client_terminates_fail_closed(profile, monkeypatch):
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
    plex = FakePlexServer(sessions=[session], clients=[])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex, profile=profile)

    assert code == 0
    assert terminations == [Downshiftarr.KILL_MESSAGE_CLIENT_NOT_FOUND]


@pytest.mark.parametrize("profile", video_capable_profiles(), ids=lambda p: p.name)
def test_every_video_client_profile_remote_control_failure_terminates(profile, monkeypatch):
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
    client = FakeClient(machine_identifier=profile.machine_identifier, fail_play=True)
    plex = FakePlexServer(sessions=[session], clients=[client])

    code, terminations = run_main_with_fake_plex(monkeypatch, plex, profile=profile)

    assert code == 0
    assert terminations == [Downshiftarr.KILL_MESSAGE_SWITCH_FAIL]
    assert client.play_calls == []


def test_stale_session_lookup_retries_until_loki_session_is_visible(monkeypatch):
    profile = video_capable_profiles()[0]
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
    plex = FakePlexServer(sessions=[session], clients=[FakeClient(machine_identifier=profile.machine_identifier)])
    calls = {"count": 0}

    def delayed_sessions():
        calls["count"] += 1
        return [] if calls["count"] == 1 else [session]

    monkeypatch.setattr(plex, "sessions", delayed_sessions)
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_RETRIES", 2)
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_DELAY_S", 0)

    context = find_session(plex, InputEvent(rating_key="rk-1", session_key="session-key", machine_id=profile.machine_identifier))

    assert context is not None
    assert calls["count"] == 2


def test_session_matching_falls_back_to_session_id_when_session_key_missing(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_RETRIES", 1)
    session = protected_session()
    session.sessionKey = ""
    plex = FakePlexServer(sessions=[session])

    context = find_session(plex, InputEvent(rating_key="other", session_id="session-id"))

    assert context is not None
    assert context.session_id == "session-id"


def test_session_matching_falls_back_to_rating_key_and_username(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_RETRIES", 1)
    session = protected_session(machine_identifier=None)
    session.sessionKey = ""
    session.session.id = ""
    plex = FakePlexServer(sessions=[session])

    context = find_session(plex, InputEvent(rating_key="rk-1", username="Downshiftarr Test User"))

    assert context is not None
    assert context.username == "Downshiftarr Test User"


def test_session_matching_falls_back_to_rating_key_and_machine_id(monkeypatch):
    monkeypatch.setattr(Downshiftarr, "SESSION_LOOKUP_RETRIES", 1)
    profile = video_capable_profiles()[0]
    session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
    session.sessionKey = ""
    session.session.id = ""
    session.user.title = ""
    plex = FakePlexServer(sessions=[session])

    context = find_session(plex, InputEvent(rating_key="rk-1", machine_id=profile.machine_identifier))

    assert context is not None
    assert context.machine_id == profile.machine_identifier


def test_client_discovery_uses_player_title_lookup_when_enumeration_misses():
    session = protected_session()
    ctx = attr(
        machine_id="missing-id",
        player_title="Plex Web Chrome",
        player_address=None,
        player_port=None,
    )
    named = FakeClient(machine_identifier="named-client")
    plex = FakePlexServer(sessions=[session], clients=[], named_clients={"Plex Web Chrome": named})

    client, identifier = find_client(plex, ctx, fallback_machine_id="missing-id")

    assert client is named
    assert identifier == "named-client"


def test_termination_prefers_tautulli_before_plex_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(Downshiftarr, "terminate_via_tautulli", lambda session_key, session_id, message: calls.append("tautulli") or True)
    monkeypatch.setattr(Downshiftarr, "plex_terminate_session", lambda session_item, session_id, reason: calls.append("plex") or True)
    ev = InputEvent(session_key="session-key", session_id="session-id")
    ctx = attr(session_key="session-key", session_id="session-id", session_item=object())

    assert Downshiftarr.terminate_best_effort(None, ev, ctx, "test")
    assert calls == ["tautulli"]


def test_termination_uses_plex_fallback_when_tautulli_fails(monkeypatch):
    calls = []
    monkeypatch.setattr(Downshiftarr, "terminate_via_tautulli", lambda session_key, session_id, message: calls.append("tautulli") or False)
    monkeypatch.setattr(Downshiftarr, "plex_terminate_session", lambda session_item, session_id, reason: calls.append("plex") or True)
    ev = InputEvent(session_key="session-key", session_id="session-id")
    ctx = attr(session_key="session-key", session_id="session-id", session_item=object())

    assert Downshiftarr.terminate_best_effort(None, ev, ctx, "test")
    assert calls == ["tautulli", "plex"]


def test_accessory_profiles_do_not_enforce_when_no_video_transcode_is_reported(monkeypatch):
    accessories = [profile for profile in CLIENT_PROFILES if not profile.video_capable]
    for profile in accessories:
        session = protected_session(profile=profile, machine_identifier=profile.machine_identifier)
        plex = FakePlexServer(sessions=[session], clients=[FakeClient(machine_identifier=profile.machine_identifier)])

        code, terminations = run_main_with_fake_plex(monkeypatch, plex, profile=profile, video_decision="direct play", dynamic_range="SDR")

        assert code == 0
        assert terminations == []
