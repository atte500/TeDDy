import os
import sys
import pytest
from pathlib import Path
from textwrap import dedent
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.domain.models.config_schema import DEFAULT_APP_CONFIG
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


@pytest.fixture
def env(monkeypatch, tmp_path: Path):
    """Provides a fresh Test Harness anchored to tmp_path."""
    return TestEnvironment(monkeypatch, tmp_path).setup()


def test_repo_tree_generator_produces_correct_format(env, tmp_path):
    """Verify correct tree formatting in recursive (ls -R) style."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").touch()

    generator = env.get_service(IRepoTreeGenerator)

    expected_tree = dedent(
        """
        docs
        src

        ./docs:
        guide.md

        ./src:
        main.py
        """
    ).strip()

    tree_output = generator.generate_tree()
    assert tree_output.strip() == expected_tree


def test_repo_tree_generator_orders_sections_by_relative_path(env, tmp_path):
    """Verify section order follows the relative path sort around the root."""
    (tmp_path / "!important").mkdir()
    (tmp_path / "!important" / "top.txt").touch()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "README.md").touch()

    generator = env.get_service(IRepoTreeGenerator)

    expected_tree = dedent(
        """
        ./!important:
        top.txt

        !important
        README.md
        src

        ./src:
        main.py
        """
    ).strip()

    tree_output = generator.generate_tree()
    assert tree_output.strip() == expected_tree


def test_repo_tree_generator_respects_gitignore(env, tmp_path):
    """Verify that .gitignore patterns are respected."""
    (tmp_path / ".gitignore").write_text(".venv/\ndist/\nlog.txt", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib").touch()
    (tmp_path / "log.txt").touch()

    generator = env.get_service(IRepoTreeGenerator)
    tree_output = generator.generate_tree()

    assert "main.py" in tree_output
    assert ".venv" not in tree_output
    assert "log.txt" not in tree_output


def test_tree_generator_respects_teddyignore(env, tmp_path):
    """Verify that .teddyignore patterns are respected."""
    (tmp_path / ".teddyignore").write_text("secret.md", encoding="utf-8")
    (tmp_path / "visible.txt").touch()
    (tmp_path / "secret.md").touch()

    generator = env.get_service(IRepoTreeGenerator)
    tree = generator.generate_tree()

    assert "visible.txt" in tree
    assert "secret.md" not in tree


def test_tree_generator_handles_nested_ignore(env, tmp_path):
    """Verify that ignore patterns apply to nested directories."""
    (tmp_path / ".gitignore").write_text("*.log", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "src" / "debug.log").touch()

    generator = env.get_service(IRepoTreeGenerator)
    tree = generator.generate_tree()

    assert "main.py" in tree
    assert "debug.log" not in tree


@pytest.mark.skipif(sys.platform == "win32", reason="Symlinks require admin on Windows")
@pytest.mark.timeout(5)
def test_tree_generator_handles_circular_symlinks_without_hanging(env, tmp_path):
    """
    Regression test for infinite recursion hang (Case File 14).
    Verifies that circular symlinks are treated as files and do not cause hangs.
    """
    import os

    # ARRANGE
    # root/subdir/link -> root
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    link = subdir / "circular_link"
    os.symlink(tmp_path, link)

    generator = env.get_service(IRepoTreeGenerator)

    # ACT
    # If the bug is present, this will hang and be killed by the 5s timeout
    tree_output = generator.generate_tree()

    # ASSERT
    assert "subdir" in tree_output
    assert "circular_link" in tree_output
    # The fix treats symlinks as files, so it shouldn't recurse into 'circular_link/'
    assert "./subdir/circular_link:" not in tree_output


def test_harness_default_depth_matches_the_schema_default(tmp_path, monkeypatch):
    """An implicit harness depth mirrors the schema default, not the old sentinel."""
    env = TestEnvironment(monkeypatch).setup().with_real_tree_generator(str(tmp_path))
    generator = env.get_service(IRepoTreeGenerator)

    assert generator._max_depth == DEFAULT_APP_CONFIG.context.max_depth


def test_tree_generator_renders_one_notice_when_depth_is_zero(tmp_path, monkeypatch):
    """A depth limit of zero collapses the tree to one omission notice."""
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "deep.txt").touch()

    env = (
        TestEnvironment(monkeypatch)
        .setup()
        .with_real_tree_generator(str(tmp_path), max_depth=0)
    )
    generator = env.get_service(IRepoTreeGenerator)

    tree = generator.generate_tree()

    assert tree.strip() == "[1 folder, 0 files]", tree
    assert "./a:" not in tree
    assert "deep.txt" not in tree


def test_tree_generator_marks_directories_at_the_depth_limit(tmp_path, monkeypatch):
    """A directory at the limit renders one marker with singular counts."""
    (tmp_path / "top" / "nested").mkdir(parents=True)
    (tmp_path / "top" / "one.txt").touch()
    (tmp_path / "top" / "nested" / "deep.txt").touch()

    env = (
        TestEnvironment(monkeypatch)
        .setup()
        .with_real_tree_generator(str(tmp_path), max_depth=1)
    )
    generator = env.get_service(IRepoTreeGenerator)

    tree = generator.generate_tree()

    assert "./top:" in tree
    assert "[1 folder, 1 file]" in tree
    assert "nested" not in tree
    assert "deep.txt" not in tree


def test_tree_generator_marks_plural_counts_at_a_deeper_limit(tmp_path, monkeypatch):
    """A truncated directory counts visible folders and files with plural nouns."""
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "one.txt").touch()
    (tmp_path / "a" / "b" / "two.txt").touch()
    (tmp_path / "a" / "b" / "c" / "three.txt").touch()

    env = (
        TestEnvironment(monkeypatch)
        .setup()
        .with_real_tree_generator(str(tmp_path), max_depth=2)
    )
    generator = env.get_service(IRepoTreeGenerator)

    tree = generator.generate_tree()

    assert "[1 folder, 2 files]" in tree
    assert "three.txt" not in tree


def test_tree_generator_marks_unreadable_directories(tmp_path, monkeypatch):
    """An unreadable directory renders an explicit marker, not an empty section."""
    (tmp_path / "locked").mkdir()
    (tmp_path / "locked" / "secret.txt").touch()
    (tmp_path / "readable").mkdir()
    (tmp_path / "readable" / "visible.txt").touch()

    real_scandir = os.scandir

    def guarded_scandir(path):
        if os.path.basename(os.fspath(path)) == "locked":
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)

    env = TestEnvironment(monkeypatch).setup().with_real_tree_generator(str(tmp_path))
    generator = env.get_service(IRepoTreeGenerator)

    tree = generator.generate_tree()

    assert "[unreadable]" in tree
    assert "./locked:" in tree
    assert "secret.txt" not in tree
    assert "visible.txt" in tree
