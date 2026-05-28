import os

from hypothesis import HealthCheck, settings

settings.register_profile("ci", max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
settings.register_profile("hardening", max_examples=250, suppress_health_check=[HealthCheck.too_slow], deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))
