"""MRE: does the replan request's context already carry the failure evidence?"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.services.edit_simulator import EditSimulator

VALIDATION_ERROR = (
    "Response must contain exactly one Level 1 heading and exactly one of "
    "## Action Plan or ## Message."
)
FAULTY_PLAN = "This malformed reply carries no heading at all."

REPORT_BODY = f"""# Execution Report: Malformed plan
- **Overall Status:** Validation Failed

## Validation Errors:
{VALIDATION_ERROR}

## Validation Recovery
1. Identify the root cause of the failure based on your system instructions (MRP) & context.
2. Submit a corrected plan focusing strictly on the failed/problematic action(s).
3. Defer the remaining steps of the original plan to subsequent turns.
"""


class StubTree:
    max_depth = 3
    max_children = 20

    def generate_tree(self) -> str:
        return "tree"


class StubLlm:
    def get_text_token_count(self, text: str, model: str = "") -> int:
        return len(text)


def build_workspace(root: Path) -> None:
    turn_one = root / ".teddy" / "sessions" / "s" / "01"
    turn_one.mkdir(parents=True)
    (turn_one / "plan.md").write_text(FAULTY_PLAN, encoding="utf-8")
    (turn_one / "report.md").write_text(REPORT_BODY, encoding="utf-8")
    turn_two = root / ".teddy" / "sessions" / "s" / "02"
    turn_two.mkdir()
    turn_context = "\n".join(
        [".teddy/sessions/s/01/plan.md", ".teddy/sessions/s/01/report.md"]
    )
    (turn_two / "turn.context").write_text(turn_context, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_workspace(root)
        adapter = LocalFileSystemAdapter(
            edit_simulator=EditSimulator(), root_dir=str(root)
        )

        turn_context = adapter.read_raw_file(".teddy/sessions/s/02/turn.context")
        turn_paths = [line for line in turn_context.splitlines() if line.strip()]
        scoped_paths = {"Session": [], "Turn": turn_paths}
        file_contents = adapter.read_files_in_vault(turn_paths)

        service = object.__new__(ContextService)
        service._repo_tree_generator = StubTree()
        service._file_system_manager = adapter
        service._llm_client = StubLlm()

        content = service._format_content(
            "repo-tree", scoped_paths, file_contents, ""
        )

        checks = {
            "validation error": VALIDATION_ERROR in content,
            "validation errors heading": "## Validation Errors:" in content,
            "validation recovery instruction": "## Validation Recovery" in content,
            "original faulty plan": FAULTY_PLAN in content,
        }
        print(f"turn context paths: {turn_paths}")
        for label, present in checks.items():
            print(f"request context carries {label}: {present}")

        if all(checks.values()):
            print(
                "\nMRE PASS: the replan request context already carries "
                "the failure evidence."
            )
            return
        print(
            "\nMRE FAIL: the failure evidence is not embedded in the request "
            "context."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
