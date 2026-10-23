"""Minimal reproduction: the anchoring step overrides the depth-aware factory.

The script resolves the tree generator before and after the production
project-anchoring step. A configured depth of 1 must survive both points.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

CONFIGURED_DEPTH = 1


def build_workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix="teddy-tree-depth-override-"))
    config_dir = root / ".teddy"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        f"context:\n  max_depth: {CONFIGURED_DEPTH}\n", encoding="utf-8"
    )
    nested = root / "folder1" / "folder2"
    nested.mkdir(parents=True)
    (root / "folder1" / "file1").write_text("payload 1\n", encoding="utf-8")
    (nested / "file2").write_text("payload 2\n", encoding="utf-8")
    return root


def main() -> int:
    root = build_workspace()
    os.chdir(root)

    from teddy_executor.__main__ import _ensure_project_initialized
    from teddy_executor.container import create_container
    from teddy_executor.core.ports.outbound.repo_tree_generator import (
        IRepoTreeGenerator,
    )

    container = create_container()

    before = container.resolve(IRepoTreeGenerator)
    print(f"depth before anchoring: {before._max_depth!r}")
    print(f"root before anchoring: {before.root_dir}")

    _ensure_project_initialized(container)

    after = container.resolve(IRepoTreeGenerator)
    print(f"depth after anchoring: {after._max_depth!r}")
    print(f"root after anchoring: {after.root_dir}")

    survives = (
        before._max_depth == CONFIGURED_DEPTH
        and after._max_depth == CONFIGURED_DEPTH
    )
    print(f"configured depth survives anchoring: {survives}")
    return 0 if survives else 1


if __name__ == "__main__":
    raise SystemExit(main())