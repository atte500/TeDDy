"""Contract: the bundled config.yaml declares the shipped tree limits.

Both limits must be visible in the shipped config so a user can see and
change them, not only present as a schema default.
"""

from tests.harness.setup.bundled_config import load_bundled_config


def test_bundled_config_declares_the_tree_depth_cap():
    """The shipped context group declares the depth cap of three."""
    context = load_bundled_config().get("context") or {}

    assert context.get("max_depth") == 3


def test_bundled_config_declares_the_tree_width_cap():
    """The shipped context group declares the width cap of twenty."""
    context = load_bundled_config().get("context") or {}

    assert context.get("max_children") == 20
