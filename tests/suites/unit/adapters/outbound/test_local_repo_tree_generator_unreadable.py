"""Unit tests for the unreadable-directory omission marker.

A directory whose scan raises PermissionError renders one explicit marker
instead of an ambiguous empty section, so truncation is never silent.
"""

import os

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    UNREADABLE_MARKER,
    LocalRepoTreeGenerator,
)


def _deny_scandir_for(monkeypatch, denied_name):
    """Deny only the named directory so the rest of the tree stays readable."""
    real_scandir = os.scandir

    def guarded_scandir(path):
        if os.path.basename(os.fspath(path)) == denied_name:
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)


def test_tree_generator_marks_unreadable_directories_at_the_depth_limit(
    tmp_path, monkeypatch
):
    (tmp_path / "locked").mkdir()
    (tmp_path / "locked" / "secret.txt").touch()

    generator = LocalRepoTreeGenerator(root_dir=str(tmp_path), max_depth=1)
    _deny_scandir_for(monkeypatch, "locked")

    tree = generator.generate_tree()

    assert UNREADABLE_MARKER in tree
    assert "secret.txt" not in tree
