"""Raw demo showing the desired console output layout for session execution."""
import re
import sys
from pathlib import Path

# Ensure we can import the shadow orchestrator
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_session_orchestrator import (
    _print_initial_request,
    _print_header_bar,
    _print_user_message,
)

from dataclasses import dataclass, field

@dataclass
class TestPlan:
    title: str = "Implement safety limits"
    metadata: dict = field(default_factory=lambda: {"Status": "SUCCESS 🟢"})

def extract_status_emoji(raw_status: str) -> str:
    """Mirrors the existing helper in textual_plan_reviewer_helpers.py."""
    anchored_match = re.search(r"^- \*\*Status:\*\*.*([🟢🟡🔴])", raw_status, re.MULTILINE)
    if anchored_match:
        return anchored_match.group(1)
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[0] if emojis else ""

def main():
    plan = TestPlan()
    message = "Please refactor this"
    is_session = True

    # 1. Initial Request
    _print_initial_request(message, is_session)

    # 2. Turn header + telemetry (simulated)
    import typer
    typer.secho("[01] implement-safety-limits | Planning...")
    typer.secho("• Model:    test-model")
    typer.secho("• Context:  0.0k / 128.0k tokens")
    typer.secho("• Session Cost: $0.0000")
    typer.secho("")

    # 3. Console Visibility (emoji + title)
    _print_header_bar(plan, is_session)

    # 4. Action logs (simulated, no green SUCCESS)
    typer.secho("READ - Read the main module")
    typer.secho("SUCCESS")
    typer.secho("EXECUTE - Run tests")
    typer.secho("SUCCESS")

    # 5. User Message (helper adds blank line before "User Message:")
    _print_user_message(message, is_session)

if __name__ == "__main__":
    main()