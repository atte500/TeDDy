"""Verification: a fixed anchoring step preserves the configured values.

The script imports the sandbox replica of the anchoring step and drives the
real container, so the production module stays untouched.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CONFIGURED_DEPTH = 1
CONFIGURED_READ_LINES = 7


def build_workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix="teddy-tree-depth-fixed-"))
    config_dir = root / ".teddy"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "context:\n  max_tree_depth: 1\nread:\n  max_lines: 7\n", encoding="utf-8"
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

    from replica_main import ensure_project_initialized

    from teddy_executor.container import create_container
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )
    from teddy_executor.core.ports.outbound.repo_tree_generator import (
        IRepoTreeGenerator,
    )

    container = create_container()
    ensure_project_initialized(container)

    config = container.resolve(IConfigService)
    print(f"configured depth: {config.get_setting('context.max_tree_depth', 0)!r}")

    generator = container.resolve(IRepoTreeGenerator)
    filesystem = container.resolve(IFileSystemManager)
    print(f"generator depth: {generator._max_depth!r}")
    print(f"filesystem read cap: {filesystem.max_read_lines!r}")

    tree = generator.generate_tree()
    print("--- rendered tree ---")
    print(tree)
    print("--- end tree ---")

    depth_ok = generator._max_depth == CONFIGURED_DEPTH
    read_ok = filesystem.max_read_lines == CONFIGURED_READ_LINES
    marker_present = "depth limit 1" in tree
    truncated = "folder2" not in tree
    print(f"depth preserved: {depth_ok}")
    print(f"read cap preserved: {read_ok}")
    print(f"omission marker present: {marker_present}")
    print(f"deeper levels truncated: {truncated}")
    return 0 if (depth_ok and read_ok and marker_present and truncated) else 1


if __name__ == "__main__":
    raise SystemExit(main())