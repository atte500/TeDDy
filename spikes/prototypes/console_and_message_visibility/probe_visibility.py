#!/usr/bin/env python3
"""
Probe for Console & Message Visibility (Phase 2).

Creates a temporary session directory, monkey-patches SessionOrchestrator.execute()
to add emoji+title before action logs and user message after action logs,
drives the CLI via CliRunner with -y flag, and verifies the terminal output.

Scenarios:
    --scenario 1 (default): Emoji + Title only (no user message)
    --scenario 2: Emoji + Title + simulated User Message
"""

import sys
import os
import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from typer.testing import CliRunner
from teddy_executor.__main__ import app
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator

# Import the wrapper from the shadow file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_session_orchestrator import wrap_execute, _echo_user_message

import typer


def _setup_session_dir() -> Path:
    """Creates a temporary session directory with meta.yaml and plan.md.
    Returns the path to the plan.md file.
    """
    session_root = Path(tempfile.mkdtemp())
    turn_dir = session_root / "turn_001"
    turn_dir.mkdir(parents=True, exist_ok=True)

    # meta.yaml signals session mode
    meta_content = """agent_name: developer
model: test-model
turn_cost: 0.0
cumulative_cost: 0.0
"""
    meta_path = session_root / "meta.yaml"
    meta_path.write_text(meta_content, encoding="utf-8")

    # plan.md with a READ action
    plan_content = """# Test Plan Title
- **Agent:** Developer
- **Status:** To De-risk

## Rationale
```
Test plan for visibility probe.
```

## Action Plan

### `READ`
- **File Path:** [README.md](/README.md)
- **Description:** Read the project readme.
"""
    plan_path = turn_dir / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    return plan_path


def run_scenario_1() -> tuple[str, str]:
    """
    Scenario 1: Emoji + Title printed before action logs.
    No user message. Uses monkey-patch on SessionOrchestrator.execute().
    Returns (stdout, stderr) tuple.
    """
    original_execute = SessionOrchestrator.execute
    patched_execute = wrap_execute(original_execute)

    plan_path = _setup_session_dir()

    with patch.object(SessionOrchestrator, 'execute', patched_execute):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            ["execute", str(plan_path), "-y", "--no-copy"],
            catch_exceptions=False,
        )
    return result.stdout, result.stderr


def run_scenario_2() -> tuple[str, str]:
    """
    Scenario 2: Emoji + Title before action logs, User Message after.
    The user message is provided via the CLI `-m` flag, which flows through
    ExecutionOrchestrator into the report metadata. The monkey-patched
    SessionOrchestrator.execute() will then print it after execution.
    Returns (stdout, stderr) tuple.
    """
    original_execute = SessionOrchestrator.execute
    patched_execute = wrap_execute(original_execute)

    plan_path = _setup_session_dir()

    with patch.object(SessionOrchestrator, 'execute', patched_execute):
        runner = CliRunner(mix_stderr=False)
        # Pass -m "Fix the index" to inject the user message
        result = runner.invoke(
            app,
            ["execute", str(plan_path), "-y", "--no-copy", "-m", "Fix the index"],
            catch_exceptions=False,
        )
    return result.stdout, result.stderr


def verify_scenario_1(stdout: str, stderr: str) -> None:
    """Assertions for Scenario 1 (emoji+title only)."""
    assert "🟢" in stderr, "Emoji should be present in stderr"
    assert "Test Plan Title" in stderr, "Plan title should be present in stderr"
    assert "User Message:" not in stderr, "No User Message line should appear in stderr"
    # Verify execution report in stdout
    assert "SUCCESS" in stdout, "Execution report should have SUCCESS in stdout"
    assert "🟢" not in stdout, "Emoji should NOT be in stdout (execution report)"


def verify_scenario_2(stdout: str, stderr: str) -> None:
    """Assertions for Scenario 2 (emoji+title + user message)."""
    assert "🟢" in stderr, "Emoji should be present in stderr"
    assert "Test Plan Title" in stderr, "Plan title should be present in stderr"
    assert "User Message:" in stderr, "User Message: line should appear in stderr"
    assert "Fix the index" in stderr, "User message content should appear in stderr"
    # Verify relative order in stderr: emoji+title should appear before User Message:
    emoji_pos = stderr.find("🟢")
    msg_pos = stderr.find("User Message:")
    assert emoji_pos < msg_pos, "Emoji line must appear before User Message in stderr"
    # Verify user message content is on the line immediately after "User Message:" label
    lines = stderr.split('\n')
    msg_label_idx = next(i for i, line in enumerate(lines) if "User Message:" in line)
    assert msg_label_idx + 1 < len(lines), "Content line must exist after label"
    assert "Fix the index" in lines[msg_label_idx + 1], "Content must be on next line after label"
    # Verify execution report in stdout
    assert "SUCCESS" in stdout, "Execution report should have SUCCESS in stdout"
    assert "🟢" not in stdout, "Emoji should NOT be in stdout (execution report)"


def main():
    parser = argparse.ArgumentParser(description="Visibility Probe - Phase 2 Demo")
    parser.add_argument(
        "--scenario", type=int, default=1, choices=[1, 2],
        help="Scenario: 1=Emoji+Title only, 2=Emoji+Title + User Message"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Run verification assertions, don't print output"
    )
    args = parser.parse_args()

    if args.scenario == 1:
        stdout, stderr = run_scenario_1()
        verify_scenario_1(stdout, stderr)
        if not args.verify:
            print("=== SCENARIO 1: Emoji + Title (no user message) ===")
            print("STDERR:", repr(stderr))
            print("STDOUT (first 200 chars):", repr(stdout[:200]))
        print("=== SCENARIO 1 ASSERTIONS PASSED ===")
        print("  ✅ Emoji (🟢) is present in stderr")
        print("  ✅ Plan title is present in stderr")
        print("  ✅ No User Message line printed")
        print("  ✅ Execution report in stdout")

    elif args.scenario == 2:
        stdout, stderr = run_scenario_2()
        verify_scenario_2(stdout, stderr)
        if not args.verify:
            print("=== SCENARIO 2: Emoji + Title + User Message ===")
            print("STDERR:", repr(stderr))
            print("STDOUT (first 200 chars):", repr(stdout[:200]))
        print("=== SCENARIO 2 ASSERTIONS PASSED ===")
        print("  ✅ Emoji (🟢) is present in stderr")
        print("  ✅ Plan title is present in stderr")
        print("  ✅ User Message: line is present in stderr")
        print("  ✅ User message content appears")
        print("  ✅ User Message appears after emoji+title in stderr")
        print("  ✅ Execution report in stdout")


if __name__ == "__main__":
    main()
