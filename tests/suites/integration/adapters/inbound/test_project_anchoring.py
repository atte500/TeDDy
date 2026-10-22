"""Integration: project anchoring preserves the configured tree depth.

The anchoring step re-registers IRepoTreeGenerator so adapters resolve against
the detected project root. That re-registration must forward
``context.max_tree_depth``; otherwise it falls back to the constructor default
and renders the whole tree, silently discarding the user value.
"""

from pathlib import Path

from teddy_executor.__main__ import _ensure_project_initialized
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator

CONFIGURED_DEPTH = 1


def _write_configured_workspace(root: Path) -> None:
    """Writes a depth-1 config and a tree deep enough to exceed the limit."""
    teddy_dir = root / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    (teddy_dir / "config.yaml").write_text(
        f"context:\n  max_tree_depth: {CONFIGURED_DEPTH}\n",
        encoding="utf-8",
    )
    deep = root / "folder1" / "folder2"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("payload\n", encoding="utf-8")
    (root / "folder1" / "shallow.txt").write_text("payload\n", encoding="utf-8")


def test_anchoring_preserves_configured_tree_depth(container, tmp_path: Path) -> None:
    """Anchoring resolves the configured depth and truncates the rendered tree."""
    # Arrange
    _write_configured_workspace(tmp_path)

    # Act
    _ensure_project_initialized(container, root_dir=str(tmp_path))
    generator = container.resolve(IRepoTreeGenerator)
    tree = generator.generate_tree()

    # Assert
    assert generator._max_depth == CONFIGURED_DEPTH, (
        f"Anchoring discarded the configured depth: {generator._max_depth}"
    )
    assert "[... directory not expanded (depth limit 1)" in tree, tree
    assert "folder2" not in tree, tree
