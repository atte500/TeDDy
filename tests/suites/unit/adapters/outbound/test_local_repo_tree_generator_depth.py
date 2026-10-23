"""Unit tests for the tree generator depth contract.

The constructor accepts a non-negative depth limit and defaults to the schema
default. A directory at the limit renders one omission marker instead of
expanding, and zero is a literal cap.
"""

import pytest

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.core.domain.models.config_schema import DEFAULT_APP_CONFIG


def test_tree_generator_defaults_to_the_schema_default(tmp_path):
    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    assert generator._max_depth == DEFAULT_APP_CONFIG.context.max_depth


@pytest.mark.parametrize("max_depth", [1, 2, 5])
def test_tree_generator_stores_configured_max_depth(tmp_path, max_depth):
    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=max_depth)

    assert generator._max_depth == max_depth
