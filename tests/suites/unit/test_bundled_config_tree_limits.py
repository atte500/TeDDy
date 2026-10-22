"""Contract: the bundled config.yaml declares the shipped tree width cap.

The width cap must be visible in the shipped config so a user can see and
change it, not only present as a schema default.
"""

from tests.harness.setup.bundled_config import load_bundled_config


def test_bundled_config_declares_the_tree_width_cap():
    """The shipped context group declares the width cap of twenty."""
    context = load_bundled_config().get("context") or {}

    assert context.get("max_tree_width") == 20
