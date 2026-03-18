from pathlib import Path
from textwrap import dedent


def test_repo_tree_generator_produces_correct_format(tmp_path: Path):
    """
    Tests that the tree generator produces a correctly formatted and indented
    string representation of the directory structure.
    """
    from teddy_executor.adapters.outbound.local_repo_tree_generator import (
        LocalRepoTreeGenerator,
    )

    # Arrange
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "src" / "utils.py").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").touch()
    (tmp_path / "README.md").touch()

    # .gitignore to ignore nothing for this test
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")

    adapter = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    expected_tree = dedent(
        """
        docs/
          guide.md
        src/
          main.py
          utils.py
        README.md
        """
    ).strip()

    # Act
    tree_output = adapter.generate_tree()

    # Assert
    assert tree_output.strip() == expected_tree


def test_repo_tree_generator_respects_gitignore(tmp_path: Path):
    """
    Tests that LocalRepoTreeGenerator correctly generates a file tree
    and respects rules from a .gitignore file.
    """
    from teddy_executor.adapters.outbound.local_repo_tree_generator import (
        LocalRepoTreeGenerator,
    )

    # Arrange
    # Create a test directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").touch()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").touch()

    # Create ignored files and directories
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib").touch()
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "package.whl").touch()
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "cache.pyc").touch()
    (tmp_path / "log.txt").touch()

    # Create .gitignore with the corrected pattern
    gitignore_content = dedent(
        """
        # Python stuff
        .venv/
        __pycache__/

        # Build artifacts
        dist/

        # Log files
        log.txt
    """
    )
    (tmp_path / ".gitignore").write_text(gitignore_content, encoding="utf-8")

    adapter = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    # Act
    tree_output = adapter.generate_tree()

    # Assert
    # Check that included files are present
    assert "src/" in tree_output
    assert "main.py" in tree_output
    assert "docs/" in tree_output
    assert "guide.md" in tree_output
    assert "tests/" in tree_output
    assert "test_main.py" in tree_output

    # Check that ignored files and directories are NOT present
    assert ".venv" not in tree_output
    assert "dist" not in tree_output
    assert "__pycache__" not in tree_output
    assert "log.txt" not in tree_output
    assert "package.whl" not in tree_output
