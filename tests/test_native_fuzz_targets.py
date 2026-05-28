from pathlib import Path

import pytest

from scripts.testing import run_native_fuzz

pytestmark = [pytest.mark.native_fuzz]


def test_native_fuzz_targets_exist_and_use_python311_lane():
    repo_root = Path(__file__).resolve().parents[1]

    for name in run_native_fuzz.target_names():
        target = run_native_fuzz.find_target(name)
        command = run_native_fuzz.build_command(target, runs=10, max_total_time=1)
        assert (repo_root / target.path).exists()
        assert command[:7] == ["uv", "run", "--isolated", "--python", "3.11", "--group", "native-fuzz"]
        assert "-runs=10" in command
        assert "-max_total_time=1" in command
