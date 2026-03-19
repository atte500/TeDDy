import time
from pathlib import Path
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


def test_repo_tree_generator_performance_with_large_ignored_dir(
    tmp_path: Path, monkeypatch
):
    """
    Tests that the tree generator is efficient even when large directories are ignored.
    """
    # Arrange
    ignored_dir = tmp_path / ".venv"
    ignored_dir.mkdir()
    for i in range(5000):
        (ignored_dir / f"file_{i}.py").touch()

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").touch()

    (tmp_path / ".gitignore").write_text(".venv/", encoding="utf-8")

    env = TestEnvironment(monkeypatch).setup().with_real_tree_generator(str(tmp_path))
    generator = env.get_service(IRepoTreeGenerator)  # type: ignore[type-abstract]

    # Act
    start_time = time.perf_counter()
    tree_output = generator.generate_tree()
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000

    # Assert
    assert ".venv" not in tree_output
    assert "src/" in tree_output
    assert "main.py" in tree_output

    # Performance: Should be very fast (< 200ms)
    max_duration_ms = 200
    assert duration_ms < max_duration_ms, (
        f"Tree generation took too long: {duration_ms:.2f}ms"
    )


def test_tree_integrity_with_deep_unignored_file(tmp_path: Path, monkeypatch):
    """
    Tests that deep files correctly include their parent directories in the tree.
    """
    # Arrange
    deep_dir = tmp_path / "a" / "b" / "c"
    deep_dir.mkdir(parents=True)
    (deep_dir / "file.txt").touch()

    env = TestEnvironment(monkeypatch).setup().with_real_tree_generator(str(tmp_path))
    generator = env.get_service(IRepoTreeGenerator)  # type: ignore[type-abstract]

    # Act
    tree_output = generator.generate_tree()

    # Assert
    assert "a/" in tree_output
    assert "  b/" in tree_output
    assert "    c/" in tree_output
    assert "      file.txt" in tree_output
