import pytest

import Downshiftarr
from Downshiftarr import InputEvent, find_client, find_session, pick_best_fallback_media_index, plex_terminate_session
from tests.harness.client_profiles import CLIENT_PROFILES
from tests.harness.fakes import FakeClient, FakePlexServer, attr, media

pytestmark = [pytest.mark.simulated]


def protected_session(*, machine_identifier: str | None = "client-plex-web", view_offset: int = 1234):
    player = attr(title="Plex Web Chrome", product="Plex Web", platform="Chrome", viewOffset=view_offset)
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


def run_main_with_fake_plex(monkeypatch, plex):
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
            "--machine-id=client-plex-web",
            "--video-decision=transcode",
            "--video-dynamic-range=HDR",
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
