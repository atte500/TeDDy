"""Unit tests for the per-directory width cap.

A non-root directory holding more visible entries than the cap renders one
compact notice instead of its children, so a wide shallow folder cannot
dominate the payload. The cap is a maximum, so a directory holding exactly the
cap count expands. The project root is exempt, because it is the only place
where a top-level file is named. A withheld directory omits its descendant
sections, because names without their parent folder cannot be mapped.
"""

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)


def test_width_cap_withholds_a_directory_above_the_cap(tmp_path):
    """A directory above the cap renders one notice and no child names."""
    wide = tmp_path / "wide"
    wide.mkdir()
    for index in range(6):
        (wide / f"w-{index:02d}.txt").touch()
    narrow = tmp_path / "narrow"
    narrow.mkdir()
    (narrow / "n-00.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_children=5)
    tree = generator.generate_tree()

    assert "./wide:" in tree, tree
    assert "[0 folders, 6 files]" in tree, tree
    assert "w-00.txt" not in tree, tree
    assert "n-00.txt" in tree, tree


def test_width_cap_expands_a_directory_at_exactly_the_cap(tmp_path):
    """The cap is a maximum, so a directory at the cap expands."""
    exact = tmp_path / "exact"
    exact.mkdir()
    for index in range(5):
        (exact / f"e-{index:02d}.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_children=5)
    tree = generator.generate_tree()

    assert "e-00.txt" in tree, tree
    assert "[0 folders, 5 files]" not in tree, tree


def test_width_cap_leaves_the_root_listing_uncapped(tmp_path):
    """The project root lists every entry even above the cap."""
    for index in range(6):
        (tmp_path / f"root-{index:02d}.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_children=1)
    tree = generator.generate_tree()

    for index in range(6):
        assert f"root-{index:02d}.txt" in tree, tree


def test_withheld_directory_omits_its_child_sections(tmp_path):
    """A withheld directory renders one notice and drops its descendants."""
    wide = tmp_path / "wide"
    child = wide / "child"
    child.mkdir(parents=True)
    (child / "leaf.txt").touch()
    for index in range(4):
        (wide / f"w-{index:02d}.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_children=3)
    tree = generator.generate_tree()

    assert "./wide:" in tree, tree
    assert "[1 folder, 4 files]" in tree, tree
    assert "./wide/child:" not in tree, tree
    assert "leaf.txt" not in tree, tree
