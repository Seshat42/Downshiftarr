from pathlib import Path

import pytest
import tomllib

from scripts.testing import run_mutation

pytestmark = [pytest.mark.mutation]


def test_mutmut_configuration_targets_downshiftarr_core():
    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["tool"]["mutmut"]["paths_to_mutate"] == ["Downshiftarr.py"]
    assert data["tool"]["mutmut"]["pytest_add_cli_args_test_selection"] == ["tests"]


def test_mutation_runner_requires_manual_execution_for_campaign(monkeypatch):
    monkeypatch.delenv(run_mutation.MANUAL_ENV, raising=False)

    assert run_mutation.main(["--target", "downshiftarr-core", "--run"]) == 2
