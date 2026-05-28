import importlib
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pytest_registers_hardening_markers():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = "\n".join(data["tool"]["pytest"]["ini_options"]["markers"])

    for marker in ("property", "fuzz", "native_fuzz", "monkey", "chaos", "mutation", "boundary"):
        assert f"{marker}:" in markers


def test_hardening_catalog_covers_every_requested_category():
    catalog = importlib.import_module("scripts.testing.hardening_catalog")

    categories = {run.category for run in catalog.all_runs()}

    assert {"property", "fuzz", "native_fuzz", "monkey", "chaos", "mutation", "boundary"} <= categories
    assert catalog.validate_catalog() == []


def test_hardening_run_list_prints_required_manual_commands():
    completed = subprocess.run(
        [sys.executable, "scripts/testing/list_hardening_runs.py", "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    assert "uv run pytest -m boundary" in output
    assert "uv run pytest -m property" in output
    assert "uv run pytest -m fuzz" in output
    assert "uv run --python 3.11 python scripts/testing/run_native_fuzz.py --list-targets" in output
    assert "uv run python scripts/testing/run_monkey.py --list-scenarios" in output
    assert "uv run python scripts/testing/run_chaos.py --list-scenarios" in output
    assert "uv run python scripts/testing/run_mutation.py --list-targets" in output


def test_hardening_runners_default_to_listing_or_dry_run_only():
    native_fuzz = importlib.import_module("scripts.testing.run_native_fuzz")
    monkey = importlib.import_module("scripts.testing.run_monkey")
    chaos = importlib.import_module("scripts.testing.run_chaos")
    mutation = importlib.import_module("scripts.testing.run_mutation")

    assert native_fuzz.main(["--list-targets"]) == 0
    assert monkey.main(["--list-scenarios"]) == 0
    assert chaos.main(["--list-scenarios"]) == 0
    assert mutation.main(["--list-targets"]) == 0
    assert mutation.main(["--target", "downshiftarr-core", "--dry-run"]) == 0


def test_verify_hardening_setup_builds_non_campaign_checks():
    verify = importlib.import_module("scripts.testing.verify_hardening_setup")

    checks = verify.build_checks()
    names = [check.name for check in checks]

    assert "hardening-run-list" in names
    assert "hardening-pytest-collect" in names
    assert "atheris-python311-import" in names
    assert "mutmut-import" in names
    assert all("run_mutation.py" not in " ".join(check.command) or "--list-targets" in check.command for check in checks)


def test_hardening_secret_redaction_masks_environment_values(monkeypatch):
    catalog = importlib.import_module("scripts.testing.hardening_catalog")
    monkeypatch.setenv("PLEX_TOKEN", "super-secret-token")
    monkeypatch.setenv("TAUTULLI_APIKEY", "api-secret")

    text = catalog.redact_secrets("token=super-secret-token apikey=api-secret")

    assert "super-secret-token" not in text
    assert "api-secret" not in text
    assert "[REDACTED]" in text


def test_verify_local_excludes_manual_hardening_campaigns_by_default():
    from scripts.testing import verify_local

    gates = verify_local.build_gates(python_version="3.12", gitleaks_bin="gitleaks")
    non_destructive = next(gate for gate in gates if gate.name == "tests-non-destructive")
    marker_expression = non_destructive.command[-1]

    for marker in ("property", "fuzz", "native_fuzz", "monkey", "chaos", "mutation", "boundary"):
        assert f"not {marker}" in marker_expression


def test_verify_local_can_add_setup_only_hardening_check():
    from scripts.testing import verify_local

    gates = verify_local.build_gates(python_version="3.12", gitleaks_bin="gitleaks", hardening_setup=True)

    assert "hardening-setup" in [gate.name for gate in gates]
    hardening_gate = next(gate for gate in gates if gate.name == "hardening-setup")
    assert hardening_gate.command == [verify_local.sys.executable, "scripts/testing/verify_hardening_setup.py"]


def test_hardening_artifact_paths_are_ignored():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    for entry in (".hypothesis/", ".mutmut-cache/", "artifacts/hardening/"):
        assert entry in gitignore


def test_hardening_runners_do_not_emit_known_secret_values(monkeypatch, capsys):
    monkeypatch.setenv("PLEX_TOKEN", "token-that-must-not-print")
    monkeypatch.setenv("TAUTULLI_APIKEY", "key-that-must-not-print")

    monkey = importlib.import_module("scripts.testing.run_monkey")
    chaos = importlib.import_module("scripts.testing.run_chaos")

    assert monkey.main(["--list-scenarios"]) == 0
    assert chaos.main(["--list-scenarios"]) == 0
    captured = capsys.readouterr()

    assert "token-that-must-not-print" not in captured.out
    assert "key-that-must-not-print" not in captured.out
