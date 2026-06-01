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
        "github-storage-only",
        "diff-check",
    ]
    assert gates[0].command == ["git", "status", "--short", "--branch", "--untracked-files=all"]
    assert gates[1].command == ["uv", "sync", "--all-groups", "--python", "3.12", "--locked"]
    assert gates[2].command == [
        "uv",
        "run",
        "--locked",
        "pytest",
        "-m",
        verify_local.non_destructive_marker_expression(),
    ]
    assert gates[8].command == [verify_local.sys.executable, "scripts/testing/verify_local.py", "--bandit-check-only"]
    assert gates[9].command[:3] == ["gitleaks", "detect", "--source"]
    assert gates[-2].command == [verify_local.sys.executable, "scripts/testing/verify_local.py", "--storage-only-check-only"]


def test_build_gates_adds_ci_hygiene_when_requested():
    gates = verify_local.build_gates(python_version="3.12", gitleaks_bin="gitleaks", ci=True)

    assert [gate.name for gate in gates][-3:] == [
        "secret-hygiene",
        "github-storage-only",
        "diff-check",
    ]
    assert gates[-3].command == [verify_local.sys.executable, "scripts/testing/verify_secret_hygiene.py"]


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


def test_bandit_baseline_normalization_uses_current_platform_separator():
    baseline = {
        "metrics": {"./Downshiftarr.py": {}, ".\\Plex Transcoder": {}, "_totals": {}},
        "results": [
            {"filename": "./Downshiftarr.py", "test_id": "B110"},
            {"filename": ".\\Plex Transcoder", "test_id": "B310"},
        ],
    }

    normalized = verify_local.normalize_bandit_baseline_for_platform(baseline)

    assert "." + verify_local.os.sep + "Downshiftarr.py" in normalized["metrics"]
    assert "." + verify_local.os.sep + "Plex Transcoder" in normalized["metrics"]
    assert "_totals" in normalized["metrics"]
    assert [entry["filename"] for entry in normalized["results"]] == [
        "." + verify_local.os.sep + "Downshiftarr.py",
        "." + verify_local.os.sep + "Plex Transcoder",
    ]


def test_bandit_check_only_skips_external_tool_detection(monkeypatch):
    monkeypatch.setattr(verify_local, "missing_required_tools", lambda: pytest.fail("tool detection should not run"))
    monkeypatch.setattr(verify_local, "run_bandit_check", lambda: 0)

    assert verify_local.main(["--bandit-check-only"]) == 0


def test_main_exits_before_gates_when_required_tools_missing(monkeypatch):
    monkeypatch.setattr(verify_local, "missing_required_tools", lambda: ["uv"])
    monkeypatch.setattr(verify_local, "run_gate", lambda gate: pytest.fail("gates should not run when tools are missing"))

    assert verify_local.main([]) == 127


def test_main_stops_at_first_failing_gate(monkeypatch):
    gates = [verify_local.Gate("first", ["true"]), verify_local.Gate("second", ["false"])]
    calls = []
    monkeypatch.setattr(verify_local, "missing_required_tools", lambda: [])
    monkeypatch.setattr(verify_local, "build_gates", lambda python_version, ci=False, hardening_setup=False: gates)

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


def test_storage_only_check_rejects_github_workflows(tmp_path, monkeypatch):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "security-ci.yml").write_text("name: ci\n", encoding="utf-8")
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_local, "tracked_github_paths", lambda: [])
    monkeypatch.setattr(verify_local, "remote_branch_names", lambda: ["origin/main"])

    assert verify_local.run_storage_only_check() == 1


def test_storage_only_check_rejects_tracked_github_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_local, "tracked_github_paths", lambda: [".github/workflows/security-ci.yml"])
    monkeypatch.setattr(verify_local, "remote_branch_names", lambda: ["origin/main"])

    assert verify_local.run_storage_only_check() == 1


def test_storage_only_check_rejects_non_main_remote_branch(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_local, "tracked_github_paths", lambda: [])
    monkeypatch.setattr(verify_local, "remote_branch_names", lambda: ["origin/main", "origin/codex/test"])

    assert verify_local.run_storage_only_check() == 1


def test_storage_only_check_accepts_main_only_without_github_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_local, "tracked_github_paths", lambda: [])
    monkeypatch.setattr(verify_local, "remote_branch_names", lambda: ["origin/main"])

    assert verify_local.run_storage_only_check() == 0


def test_storage_only_check_rejects_github_ci_wording(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("GitHub Actions security CI is the acceptance authority.\n", encoding="utf-8")
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_local, "tracked_github_paths", lambda: [])
    monkeypatch.setattr(verify_local, "remote_branch_names", lambda: ["origin/main"])

    assert verify_local.run_storage_only_check() == 1


def test_storage_only_check_rejects_ci_mirror_wording(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("CI mirror command: python scripts/testing/verify_local.py --ci\n", encoding="utf-8")
    monkeypatch.setattr(verify_local, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_local, "tracked_github_paths", lambda: [])
    monkeypatch.setattr(verify_local, "remote_branch_names", lambda: ["origin/main"])

    assert verify_local.run_storage_only_check() == 1
