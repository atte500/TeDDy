import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ActionLog:
    status: Any
    action_type: str
    details: Any
    failed_command: Optional[str] = None

def parse_rationale(rationale_str: str) -> List[Dict[str, str]]:
    """
    Parses rationale strings supporting both '### Section' and '1. Section' formats.
    """
    # Normalize by adding a newline to simplify lookahead
    text = "\n" + rationale_str

    # Combined regex: splits on '### ' OR '1. ' (numeric lists at start of line)
    # We use a non-capturing group for the lookahead
    sections = re.split(r"\n(?=### |\d+\.\s+)", text)

    parsed = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        lines = section.split("\n")
        title_line = lines[0]

        # Strip markers from title
        title = re.sub(r"^(###\s*|\d+\.\s*)", "", title_line).strip()
        content = "\n".join(lines[1:]).strip()

        parsed.append({"title": title, "content": content})

    return parsed

def format_action_log(log: ActionLog) -> str:
    """
    Formats an ActionLog entry to match the Jinja2 template style.
    """
    lines = [f"### `OUTCOME`: {log.status}"]

    if log.failed_command:
        lines.append(f"- **Failed Command:** `{log.failed_command}`")

    if isinstance(log.details, dict):
        if log.details.get("return_code") is not None:
            lines.append(f"- **Return Code:** `{log.details['return_code']}`")

        if log.details.get("stdout"):
            lines.append("\n#### `stdout`")
            lines.append("````text")
            lines.append(log.details["stdout"].strip())
            lines.append("````")

        if log.details.get("stderr"):
            lines.append("\n#### `stderr`")
            lines.append("````text")
            lines.append(log.details["stderr"].strip())
            lines.append("````")

        if log.details.get("diff"):
            lines.append("\n#### `diff`")
            lines.append("````diff")
            lines.append(log.details["diff"].strip())
            lines.append("````")

        # Check for generic details
        keys = ["error", "return_code", "stdout", "stderr", "content", "diff", "failed_command"]
        if not any(log.details.get(k) for k in keys):
            lines.append(f"- **Details:** `{log.details}`")
    else:
        lines.append(f"- **Details:** `{log.details}`")

    return "\n".join(lines)

# --- Test Cases ---

if __name__ == "__main__":
    print("--- 1. Testing Rationale Parsing ---")
    legacy = "### 1. Synthesis\nOld style\n### 2. Justification\nLogic here"
    modern = "1. Synthesis\nNew style\n2. Justification\nMore logic"
    mixed = "1. Synthesis\nMix it up\n### 2. Justification\nLegacy part"

    for label, raw in [("Legacy", legacy), ("Modern", modern), ("Mixed", mixed)]:
        print(f"\n[{label}]")
        for s in parse_rationale(raw):
            print(f"  Title: {s['title']}")
            print(f"  Content: {s['content'][:20]}...")

    print("\n--- 2. Testing Log Formatting ---")
    from enum import Enum
    class Status(Enum):
        SUCCESS = "SUCCESS"
        FAILURE = "FAILURE"

    log = ActionLog(
        status=Status.FAILURE,
        action_type="EXECUTE",
        failed_command="pytest",
        details={
            "return_code": 1,
            "stdout": "Test failed!",
            "stderr": "AssertionError: 1 != 2"
        }
    )
    print(format_action_log(log))
