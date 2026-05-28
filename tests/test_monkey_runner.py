import pytest

from scripts.testing import run_monkey

pytestmark = [pytest.mark.monkey]


@pytest.mark.parametrize("scenario", ["client-event-matrix", "accessory-noop", "fallback-selection"])
def test_monkey_scenarios_run_with_bounded_seed(scenario):
    result = run_monkey.run_scenario(scenario, seed=12345, iterations=5)

    assert result["iterations"] == 5
