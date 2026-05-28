from scripts.testing import verify_secret_hygiene


def test_secret_hygiene_rejects_local_secret_paths():
    findings = verify_secret_hygiene.find_path_findings(
        [
            "Downshiftarr.py",
            "Downshiftarr.env",
            "artifacts/plex-test-media/manifest.json",
            "proofs/session.png",
            "tautulli.db",
        ]
    )

    assert "forbidden local secret file: Downshiftarr.env" in findings
    assert "forbidden generated/local artifact path: artifacts/plex-test-media/manifest.json" in findings
    assert "forbidden screenshot/image proof path: proofs/session.png" in findings
    assert "forbidden local database file: tautulli.db" in findings


def test_secret_hygiene_allows_documented_examples_and_tests(tmp_path, monkeypatch):
    example = tmp_path / "Downshiftarr.env.example"
    example.write_text("PLEX_TOKEN=PUT_YOUR_PLEX_TOKEN_HERE\nTAUTULLI_APIKEY=YOUR_TAUTULLI_APIKEY_HERE\n", encoding="utf-8")
    test_file = tmp_path / "test_example.py"
    test_file.write_text('value = "PLEX_TOKEN=secret-token"\n', encoding="utf-8")

    monkeypatch.setattr(verify_secret_hygiene, "REPO_ROOT", tmp_path)

    assert verify_secret_hygiene.find_content_findings(["Downshiftarr.env.example", "test_example.py"]) == []


def test_secret_hygiene_rejects_token_like_committed_values(tmp_path, monkeypatch):
    source = tmp_path / "config.txt"
    token = "AbCdEfGhIjKlMnOp" + "QrStUvWxYz123456"
    source.write_text(f"PLEX_TOKEN={token}\n", encoding="utf-8")
    monkeypatch.setattr(verify_secret_hygiene, "REPO_ROOT", tmp_path)

    findings = verify_secret_hygiene.find_content_findings(["config.txt"])

    assert findings == ["potential committed secret in config.txt:1 for PLEX_TOKEN"]


def test_secret_hygiene_ignores_python_function_assignments(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text("api_key = configure_config_ini(config_path)\n", encoding="utf-8")
    monkeypatch.setattr(verify_secret_hygiene, "REPO_ROOT", tmp_path)

    assert verify_secret_hygiene.find_content_findings(["source.py"]) == []
