"""Unit tests for the tree generator limit contract.

The port exposes both limits as read-only properties so the context service can
state them once per section. The adapter reports the configured values, defaults
the width cap to the schema default, and rejects a non-positive cap.
"""

import pytest

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.core.domain.models.config_schema import DEFAULT_APP_CONFIG
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


def test_port_declares_both_limit_properties():
    """Both limits are read-only properties on the shared port seam."""
    assert isinstance(IRepoTreeGenerator.max_depth, property)
    assert isinstance(IRepoTreeGenerator.max_tree_width, property)


def test_adapter_defaults_the_width_cap_to_the_schema_default(tmp_path):
    """An omitted width cap mirrors the schema default."""
    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    assert generator.max_tree_width == DEFAULT_APP_CONFIG.context.max_tree_width


def test_adapter_reports_the_configured_depth(tmp_path):
    """The depth property returns the configured depth."""
    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=2)

    assert generator.max_depth == 2


@pytest.mark.parametrize("max_tree_width", [1, 20, 50])
def test_adapter_reports_the_configured_width_cap(tmp_path, max_tree_width):
    """The width property returns the configured cap."""
    generator = LocalRepoTreeGenerator(
        root_dir=str(tmp_path), max_tree_width=max_tree_width
    )

    assert generator.max_tree_width == max_tree_width


def test_adapter_rejects_a_zero_width_cap(tmp_path):
    """The width cap is a maximum, so zero is not a valid cap."""
    with pytest.raises(AssertionError, match="max_tree_width"):
        LocalRepoTreeGenerator(root_dir=str(tmp_path), max_tree_width=0)
