import pytest
from pathlib import Path
from textwrap import dedent
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


@pytest.fixture
def env(monkeypatch, tmp_path: Path):
    """Provides a fresh Test Harness anchored to tmp_path."""
    return TestEnvironment(monkeypatch, tmp_path).setup()


def test_repo_tree_generator_produces_correct_format(env, tmp_path):
    """Verify correct tree formatting and indentation."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").touch()

    generator = env.get_service(IRepoTreeGenerator)

    expected_tree = dedent(
        """
        docs/
          guide.md
        src/
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
