"""Contract: the bundled config.yaml declares the shipped plan display cap.

The cap must be visible in the shipped config so a user can see and change it,
not only present as a schema default.
"""

from tests.harness.setup.bundled_config import load_bundled_config


def test_bundled_config_declares_the_plan_max_lines_cap():
    """The shipped plan group declares the display cap of five thousand."""
    plan = load_bundled_config().get("plan") or {}

    assert plan.get("max_lines") == 5000
