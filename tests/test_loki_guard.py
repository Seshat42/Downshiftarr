from urllib.error import HTTPError

import pytest

from scripts.testing.loki_guard import LokiIdentity, assert_loki_identity, build_plex_request, is_loopback_url, parse_identity_xml

pytestmark = [pytest.mark.simulated]


def test_loki_guard_allows_only_loopback_urls():
    assert is_loopback_url("http://127.0.0.1:32400")
    assert is_loopback_url("http://localhost:32400")
    assert not is_loopback_url("https://bragi.example.com:32400")
    assert not is_loopback_url("http://toob.example.com:32400")


def test_loki_guard_rejects_non_loki_identity():
    identity = LokiIdentity(machine_identifier="wrong", version="1.0", claimed=True)

    with pytest.raises(RuntimeError, match="Unexpected Plex machineIdentifier"):
        assert_loki_identity(
            identity,
            base_url="http://127.0.0.1:32400",
            expected_machine_identifier="165cc0187d76937eb104da8d46437bf5443ec503",
        )


def test_loki_guard_rejects_external_base_url_even_with_matching_identity():
    identity = LokiIdentity(machine_identifier="165cc0187d76937eb104da8d46437bf5443ec503", version="1.0", claimed=True)

    with pytest.raises(RuntimeError, match="Refusing non-local Plex URL"):
        assert_loki_identity(identity, base_url="https://bragi.example.com:32400")


def test_loki_guard_parses_json_identity_payload():
    identity = parse_identity_xml(
        b'{"MediaContainer":{"claimed":true,"machineIdentifier":"165cc0187d76937eb104da8d46437bf5443ec503","version":"1.0"}}'
    )

    assert identity.machine_identifier == "165cc0187d76937eb104da8d46437bf5443ec503"
    assert identity.version == "1.0"
    assert identity.claimed is True


def test_plex_request_uses_token_header_not_query():
    request = build_plex_request("http://127.0.0.1:32400", "/library/sections", token="secret-token")

    assert request.full_url == "http://127.0.0.1:32400/library/sections"
    assert request.headers["X-plex-token"] == "secret-token"
    assert "secret-token" not in request.full_url


def test_loki_guard_http_error_does_not_leak_token():
    error = HTTPError("http://127.0.0.1:32400/identity", 401, "Unauthorized", hdrs=None, fp=None)

    assert "secret-token" not in str(error)
