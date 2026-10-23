"""Minimal reproduction: context.max_depth never reaches the tree generator.

The script builds the production container exactly as the CLI does, runs the
same project-anchoring step, and then inspects the resolved tree generator.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def build_workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix="teddy-tree-depth-"))
    config_dir = root / ".teddy"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "context:\n  max_depth: 1\n", encoding="utf-8"
    )
    for depth in range(1, 5):
        folder = root
        for index in range(1, depth + 1):
            folder = folder / f"folder{index}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"file{depth}").write_text(f"payload {depth}\n", encoding="utf-8")
    return root


def main() -> int:
    root = build_workspace()
    os.chdir(root)

    from teddy_executor.__main__ import _ensure_project_initialized
    from teddy_executor.container import create_container
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.outbound.repo_tree_generator import (
        IRepoTreeGenerator,
    )

    container = create_container()
    _ensure_project_initialized(container)

    config = container.resolve(IConfigService)
    print(f"configured depth: {config.get_setting('context.max_depth', 0)!r}")

    try:
        generator = container.resolve(IRepoTreeGenerator)
    except Exception as error:  # noqa: BLE001 - probe reports the raw resolution outcome
        print(f"resolution failed: {type(error).__name__}: {error}")
        return 2

    print(f"resolved generator: {type(generator).__name__}")
    print(f"stored max depth: {getattr(generator, '_max_depth', 'missing')!r}")
    print(f"root dir: {getattr(generator, 'root_dir', 'missing')}")

    tree = generator.generate_tree()
    print("--- rendered tree ---")
    print(tree)
    print("--- end tree ---")

    marker_present = "directory not expanded" in tree
    print(f"omission marker present: {marker_present}")
    print(f"deepest folder rendered: {'folder4' in tree}")
    return 0 if marker_present else 1


if __name__ == "__main__":
    raise SystemExit(main())