"""Probe: a restored read.max_lines cap truncates session turn files.

Session orchestration reads plan.md and report.md through the capped
read_file method, while context assembly uses the uncapped vault reader.
This probe shows the two paths diverge under a low cap.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)

CAP = 7
PLAN_LINES = 20


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="teddy-session-read-cap-"))
    plan = root / "plan.md"
    plan.write_text(
        "\n".join(f"line {index}" for index in range(1, PLAN_LINES + 1)) + "\n",
        encoding="utf-8",
    )

    # read_file never touches the edit simulator, so a placeholder is enough.
    adapter = LocalFileSystemAdapter(
        edit_simulator=None,  # type: ignore[arg-type]
        root_dir=str(root),
        max_read_lines=CAP,
    )

    capped = adapter.read_file("plan.md")
    raw = adapter.read_raw_file("plan.md")

    print(f"configured cap: {CAP}")
    print(f"read_file line count: {len(capped.splitlines())}")
    print(f"read_raw_file line count: {len(raw.splitlines())}")
    print(f"session plan truncated by cap: {capped != raw}")
    return 0 if capped != raw else 1


if __name__ == "__main__":
    raise SystemExit(main())