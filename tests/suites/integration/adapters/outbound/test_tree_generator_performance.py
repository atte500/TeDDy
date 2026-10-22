import os
import sys
import time
import pytest
from pathlib import Path
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Performance tests are flaky on CI runners due to environment variance",
)
def test_repo_tree_generator_performance_with_large_ignored_dir(
    tmp_path: Path, monkeypatch
):
    """
    Tests that the tree generator is efficient even when large directories are ignored.
    """
    # Arrange
    ignored_dir = tmp_path / ".venv"
    ignored_dir.mkdir()
    for i in range(500):
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
    assert "src" in tree_output
    assert "main.py" in tree_output

    # Performance: Should be very fast (< 50ms)
    max_duration_ms = 50
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

    # The chain is three directories deep, so a depth of four is required to
    # expand the deepest directory and list its file.
    env = (
        TestEnvironment(monkeypatch)
        .setup()
        .with_real_tree_generator(str(tmp_path), max_depth=4)
    )
    generator = env.get_service(IRepoTreeGenerator)  # type: ignore[type-abstract]

    # Act
    tree_output = generator.generate_tree()

    # Assert
    assert "a" in tree_output
    assert "./a:" in tree_output
    assert "b" in tree_output
    assert "./a/b:" in tree_output
    assert "c" in tree_output
    assert "./a/b/c:" in tree_output
    assert "file.txt" in tree_output


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="A 20-level temp path chain can exceed MAX_PATH on Windows",
)
def test_depth_limit_bounds_recursion_on_a_deep_tree(tmp_path: Path, monkeypatch):
    """A depth limit stops descent, so a deep chain never fully materializes.

    The chain is far deeper than the limit. Unbounded traversal would render
    every level, so a small, fixed section count and the absence of the deepest
    node prove the limit bounds the recursion. The chain stays at 20 levels
    because macOS rejects a path above roughly 1024 bytes.
    """
    chain = tmp_path
    for level in range(20):
        chain = chain / f"d{level:03d}"
        chain.mkdir()
        (chain / f"f{level:03d}.txt").touch()
    (chain / "leaf_sentinel.txt").touch()

    env = (
        TestEnvironment(monkeypatch)
        .setup()
        .with_real_tree_generator(str(tmp_path), max_depth=3)
    )
    generator = env.get_service(IRepoTreeGenerator)  # type: ignore[type-abstract]

    tree = generator.generate_tree()

    # The deepest nodes never render, so the traversal stopped at the limit.
    assert "leaf_sentinel.txt" not in tree
    assert "d003" not in tree
    # The boundary directory renders an explicit omission marker.
    assert "./d000/d001/d002:" in tree
    assert "[1 folder, 1 file]" in tree
    # Only three nested sections render, never the full 20-level chain.
    assert tree.count("./") == 3
