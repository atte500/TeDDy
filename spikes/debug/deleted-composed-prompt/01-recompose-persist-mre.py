"""MRE: a deleted session-root composed prompt is recomposed and re-saved.

Run with:
    uv run python spikes/debug/deleted-composed-prompt/01-recompose-persist-mre.py

Desired behaviour: after the composed prompt file is gone from the session root,
reading the system prompt again recomposes it AND persists it back, so later
turns reuse it verbatim.

Drives the PRODUCTION ``PromptManager`` against a real
``LocalFileSystemAdapter`` on a temp workspace. Before the write-back existed it
exited 1 with the session root left empty; it now exits 0 and stands as the live
end-to-end check beside the unit regression test.

Exit codes: 0 = desired behaviour holds, 1 = bug reproduced.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.prompt_manager import PromptManager

AGENT_CONTENT = "<agent>PATHFINDER</agent>"
MRP_CONTENT = "<mrp>PROTOCOL</mrp>"
EXPECTED_PROMPT = f"{AGENT_CONTENT}\n\n---\n\n{MRP_CONTENT}"


def build_workspace() -> tuple[Path, Path, Path]:
    """Creates a temp project with a canonical prompt and a session whose root
    prompt is absent (simulating a deleted composed prompt)."""
    workspace = Path(tempfile.mkdtemp(prefix="teddy-deleted-prompt-mre-"))

    prompts_dir = workspace / ".teddy" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "pathfinder.md").write_text(AGENT_CONTENT, encoding="utf-8")

    session_root = workspace / ".teddy" / "sessions" / "20260101_000000-demo"
    turn_dir = session_root / "01"
    turn_dir.mkdir(parents=True)

    mrp_root = workspace / "resource_root"
    mrp_root.mkdir()
    (mrp_root / "MRP.md").write_text(MRP_CONTENT, encoding="utf-8")

    return workspace, turn_dir, session_root


def main() -> int:
    workspace, turn_dir, session_root = build_workspace()
    try:
        # edit_simulator is unused: this MRE only exercises prompt read/write.
        file_system = LocalFileSystemAdapter(
            edit_simulator=None, root_dir=str(workspace)
        )
        prompt_manager = PromptManager(
            file_system_manager=file_system,
            mrp_resource_root=workspace / "resource_root",
        )

        composed = prompt_manager.fetch_system_prompt("pathfinder", turn_dir)

        persisted_path = session_root / "pathfinder.md"
        persisted = (
            persisted_path.read_text(encoding="utf-8")
            if persisted_path.exists()
            else None
        )

        print(f"recomposed content correct: {composed == EXPECTED_PROMPT}")
        print(f"persisted at session root:   {persisted is not None}")

        if composed != EXPECTED_PROMPT:
            print("FAIL: prompt was not recomposed correctly")
            return 1
        if persisted is None:
            print(
                "FAIL: deleted composed prompt was NOT re-saved "
                "(session root stays empty; bug reproduced)"
            )
            return 1
        if persisted != EXPECTED_PROMPT:
            print("FAIL: persisted prompt does not match the composed prompt")
            return 1

        print("PASS: recomposed and re-saved the deleted composed prompt")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
