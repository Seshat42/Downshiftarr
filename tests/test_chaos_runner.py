import pytest

from scripts.testing import run_chaos

pytestmark = [pytest.mark.chaos]


@pytest.mark.parametrize("scenario", ["fake-service-faults", "client-control-faults", "malformed-metadata"])
def test_chaos_scenarios_run_with_bounded_seed(scenario):
    result = run_chaos.run_scenario(scenario, seed=24680, iterations=3)

    assert result["iterations"] == 3
