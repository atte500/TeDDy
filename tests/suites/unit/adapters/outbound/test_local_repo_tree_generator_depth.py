"""Unit tests for the tree generator depth contract.

The constructor accepts a depth limit and defaults to zero, which means
unlimited. A directory at the limit renders one omission marker instead of
expanding.
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


def test_tree_generator_marks_directories_at_the_depth_limit(tmp_path):
    (tmp_path / "top" / "nested").mkdir(parents=True)
    (tmp_path / "top" / "file.txt").touch()
    (tmp_path / "top" / "nested" / "deep.txt").touch()
    (tmp_path / "root.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=1)

    tree = generator.generate_tree()

    assert "./top:" in tree
    assert "[... directory not expanded (depth limit 1): 1 folder, 1 file]" in tree
    assert "nested" not in tree
    assert "deep.txt" not in tree


def test_tree_generator_marks_nested_directories_at_a_deeper_limit(tmp_path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "two.txt").touch()
    (tmp_path / "a" / "b" / "c" / "three.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=2)

    tree = generator.generate_tree()

    assert "[... directory not expanded (depth limit 2): 1 folder, 1 file]" in tree
    assert "three.txt" not in tree


def test_tree_generator_renders_full_tree_when_depth_is_zero(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "deep.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=0)

    tree = generator.generate_tree()

    assert "deep.txt" in tree
    assert "directory not expanded" not in tree
