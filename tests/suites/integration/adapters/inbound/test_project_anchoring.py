"""Integration: project anchoring preserves the configured tree depth.

The anchoring step re-registers IRepoTreeGenerator so adapters resolve against
the detected project root. That re-registration must forward
``context.max_depth``; otherwise it falls back to the constructor default
and renders the whole tree, silently discarding the user value.
"""

from pathlib import Path

from teddy_executor.__main__ import _ensure_project_initialized
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator

CONFIGURED_DEPTH = 1
CONFIGURED_WIDTH = 5


def _write_anchored_workspace(root: Path, depth: int, width: int | None = None) -> None:
    """Writes a config with ``depth`` and a tree deep enough to exceed it.

    An optional ``width`` adds the width cap to the same context block.
    """
    teddy_dir = root / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    lines = ["context:", f"  max_depth: {depth}"]
    if width is not None:
        lines.append(f"  max_children: {width}")
    (teddy_dir / "config.yaml").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    deep = root / "folder1" / "folder2"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("payload\n", encoding="utf-8")
    (root / "folder1" / "shallow.txt").write_text("payload\n", encoding="utf-8")


def test_anchoring_preserves_configured_tree_depth(container, tmp_path: Path) -> None:
    """Anchoring resolves the configured depth and truncates the rendered tree."""
    # Arrange
    _write_anchored_workspace(tmp_path, CONFIGURED_DEPTH)

    # Act
    _ensure_project_initialized(container, root_dir=str(tmp_path))
    generator = container.resolve(IRepoTreeGenerator)
    tree = generator.generate_tree()

    # Assert
    assert generator._max_depth == CONFIGURED_DEPTH, (
        f"Anchoring discarded the configured depth: {generator._max_depth}"
    )
    assert "[1 folder, 1 file]" in tree, tree
    assert "folder2" not in tree, tree


def test_anchoring_preserves_configured_tree_width(container, tmp_path: Path) -> None:
    """Anchoring forwards the configured width so the port reports it."""
    # Arrange
    _write_anchored_workspace(tmp_path, CONFIGURED_DEPTH, width=CONFIGURED_WIDTH)

    # Act
    _ensure_project_initialized(container, root_dir=str(tmp_path))
    generator = container.resolve(IRepoTreeGenerator)

    # Assert
    assert generator.max_children == CONFIGURED_WIDTH, (
        f"Anchoring discarded the configured width: {generator.max_children}"
    )


def test_anchoring_renders_one_notice_at_zero_depth(container, tmp_path: Path) -> None:
    """A configured depth of zero collapses the anchored tree to one notice."""
    # Arrange
    _write_anchored_workspace(tmp_path, 0)

    # Act
    _ensure_project_initialized(container, root_dir=str(tmp_path))
    generator = container.resolve(IRepoTreeGenerator)
    tree = generator.generate_tree()

    # Assert
    assert generator._max_depth == 0
    assert tree.strip() == "[1 folder, 0 files]", tree
    assert "folder1" not in tree, tree
