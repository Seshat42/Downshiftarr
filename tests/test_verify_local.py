import pytest

from scripts.testing import verify_local

pytestmark = [pytest.mark.unit]


def test_build_gates_include_official_local_verification_sequence():
    gates = verify_local.build_gates(python_version="3.12", gitleaks_bin="gitleaks")

    assert [gate.name for gate in gates] == [
        "status",
        "sync",
        "tests-non-destructive",
        "tests-simulated",
        "tests-media",
        "ruff-check",
        "ruff-format",
        "pip-audit",
        "bandit",
        "gitleaks",
        "plex-token-query-static-check",
        "diff-check",
    ]
    assert gates[0].command == ["git", "status", "--short", "--branch", "--untracked-files=all"]
    assert gates[1].command == ["uv", "sync", "--all-groups", "--python", "3.12", "--locked"]
    assert gates[2].command == ["uv", "run", "--locked", "pytest", "-m", "not loki and not browser and not destructive"]
    assert gates[9].command[:3] == ["gitleaks", "detect", "--source"]


def test_build_gates_adds_ci_hygiene_when_requested():
    gates = verify_local.build_gates(python_version="3.12", gitleaks_bin="gitleaks", ci=True)

    assert [gate.name for gate in gates][-3:] == [
        "plex-token-query-static-check",
        "secret-hygiene",
        "diff-check",
    ]
    assert gates[-2].command == [verify_local.sys.executable, "scripts/testing/verify_secret_hygiene.py"]


def test_missing_tool_detection_reports_required_tools(monkeypatch):
    monkeypatch.delenv("GITLEAKS_BIN", raising=False)
    monkeypatch.setattr(verify_local.shutil, "which", lambda tool: None if tool in {"git", "uv", "gitleaks"} else f"/usr/bin/{tool}")

    assert verify_local.missing_required_tools() == ["git", "uv", "gitleaks"]


def test_resolve_gitleaks_bin_uses_environment_override(monkeypatch):
    monkeypatch.setenv("GITLEAKS_BIN", "/opt/tools/gitleaks")

    assert verify_local.resolve_gitleaks_bin() == "/opt/tools/gitleaks"


def test_static_token_check_detects_query_string_token_construction(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text('url = base + "?X-Plex-Token=" + token\n', encoding="utf-8")
    monkeypatch.setattr(verify_local, "source_paths", lambda: [source])
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)

    assert verify_local.run_static_token_check() == 1


def test_static_token_check_allows_header_token_usage(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text('headers = {"X-Plex-Token": token}\n', encoding="utf-8")
    monkeypatch.setattr(verify_local, "source_paths", lambda: [source])
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)

    assert verify_local.run_static_token_check() == 0


def test_main_exits_before_gates_when_required_tools_missing(monkeypatch):
    monkeypatch.setattr(verify_local, "missing_required_tools", lambda: ["uv"])
    monkeypatch.setattr(verify_local, "run_gate", lambda gate: pytest.fail("gates should not run when tools are missing"))

    assert verify_local.main([]) == 127


def test_main_stops_at_first_failing_gate(monkeypatch):
    gates = [verify_local.Gate("first", ["true"]), verify_local.Gate("second", ["false"])]
    calls = []
    monkeypatch.setattr(verify_local, "missing_required_tools", lambda: [])
    monkeypatch.setattr(verify_local, "build_gates", lambda python_version, ci=False: gates)

    def fake_run_gate(gate):
        calls.append(gate.name)
        return 9 if gate.name == "first" else 0

    monkeypatch.setattr(verify_local, "run_gate", fake_run_gate)

    assert verify_local.main([]) == 9
    assert calls == ["first"]


def test_static_token_check_only_skips_external_tools(monkeypatch):
    monkeypatch.setattr(verify_local, "missing_required_tools", lambda: pytest.fail("tool detection should not run"))
    monkeypatch.setattr(verify_local, "run_static_token_check", lambda: 0)

    assert verify_local.main(["--static-token-check-only"]) == 0
