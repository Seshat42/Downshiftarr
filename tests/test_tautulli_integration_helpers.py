import pytest

from scripts.testing import run_loki_matrix

pytestmark = [pytest.mark.unit]


def test_tautulli_request_uses_api_key_parameter_without_logging_token():
    request = run_loki_matrix.build_tautulli_request("http://127.0.0.1:18181", "api-secret", "status")

    assert request.full_url == "http://127.0.0.1:18181/api/v2?apikey=api-secret&cmd=status"


def test_tautulli_health_summary_redacts_api_key():
    summary = run_loki_matrix.redact_sensitive_payload(
        {
            "tautulli_url": "http://127.0.0.1:18181",
            "tautulli_api_key": "api-secret",
            "plex_token": "plex-secret",
            "status": "ok",
        }
    )

    assert "api-secret" not in str(summary)
    assert "plex-secret" not in str(summary)
    assert summary["tautulli_api_key"] == "<redacted>"
