"""Unit tests for the tree generator depth contract.

The constructor accepts a depth limit and defaults to zero, which means
unlimited. The omission marker behavior is covered by the integration suite.
"""

import pytest

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)


def test_tree_generator_defaults_to_unlimited_depth(tmp_path):
    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    assert generator._max_depth == 0


@pytest.mark.parametrize("max_depth", [1, 2, 5])
def test_tree_generator_stores_configured_max_depth(tmp_path, max_depth):
    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=max_depth)

    assert generator._max_depth == max_depth
