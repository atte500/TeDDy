import time
from pathlib import Path
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)


def test_repo_tree_generator_performance_with_large_ignored_dir(tmp_path: Path):
    """
    Tests that the tree generator is efficient even when large directories are ignored.
    It should prune these directories and not visit their children.
    """
    # Arrange
    # Create a large ignored directory
    ignored_dir = tmp_path / ".venv"
    ignored_dir.mkdir()
    for i in range(5000):
        (ignored_dir / f"file_{i}.py").touch()

    # Create a small non-ignored directory
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").touch()

    # Create .gitignore
    (tmp_path / ".gitignore").write_text(".venv/", encoding="utf-8")

    adapter = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    # Act
    start_time = time.perf_counter()
    tree_output = adapter.generate_tree()
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000

    # Assert
    # 1. Correctness: .venv should not be in output
    assert ".venv" not in tree_output
    assert "src/" in tree_output
    assert "main.py" in tree_output

    # 2. Performance: Should be very fast (< 100ms on most systems,
    # but we'll use 200ms as a safe CI/local threshold for failing rglob)
    # The current rglob implementation will take significant time to visit 5000 files.
    max_duration_ms = 200
    assert duration_ms < max_duration_ms, (
        f"Tree generation took too long: {duration_ms:.2f}ms"
    )


def test_tree_integrity_with_deep_unignored_file(tmp_path: Path):
    """
    Tests that deep files correctly include their parent directories in the tree,
    even if the parents themselves don't have other files.
    """
    # Arrange
    deep_dir = tmp_path / "a" / "b" / "c"
    deep_dir.mkdir(parents=True)
    (deep_dir / "file.txt").touch()

    adapter = LocalRepoTreeGenerator(root_dir=str(tmp_path))

    # Act
    tree_output = adapter.generate_tree()

    # Assert
    assert "a/" in tree_output
    assert "  b/" in tree_output
    assert "    c/" in tree_output
    assert "      file.txt" in tree_output
