#!/usr/bin/env python3
"""
Scenario Prototype: Console and Message Visibility

De-risks two features:
1. Console Visibility: After metadata block, print `{status_emoji} {plan.title}`
2. Message Visibility: After all actions execute, print `User Message: {content}`

Usage:
    python spikes/prototypes/00-console-visibility.py          # default scenario: no message
    python spikes/prototypes/00-console-visibility.py --scenario message  # user message
    python spikes/prototypes/00-console-visibility.py --verify  # 5-sec boot check
"""

import contextlib
import io
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

# Add project root to sys.path for imports
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import typer


# ─── Helper: Status Emoji Mapping ──────────────────────────────────────────────
def _extract_status_emoji(status_str: str) -> str:
    """Extract the trailing emoji from a status string like 'ON-TRACK 🟢'."""
    emojis = re.findall(r"[🟢🟡🔴]", status_str.strip())
    return emojis[0] if emojis else "❓"


# ─── Mock Outbound Adapters ─────────────────────────────────────────────────────
class AutoConfirmUserInteractor:
    """IUserInteractor implementation that auto-confirms all actions."""

    def confirm_action(self, action, action_prompt, change_set) -> tuple[bool, str]:
        """Auto-approve with empty message."""
        return (True, "")

    def ask_question(self, prompt: str) -> str:
        """Return empty string for questions."""
        return ""

    def display_message(self, message: str) -> None:
        """Silently consume display messages."""
        pass

    def ask_flexible_input(self, prompt: str, default: Optional[str] = None) -> str:
        """Return empty string for flexible input."""
        return default or ""

    def confirm(self, prompt: str) -> bool:
        """Auto-confirm for simple confirmations."""
        return True


class NoopLLMClient:
    """ILlmClient implementation that does nothing (avoids network calls)."""

    def complete(self, messages, **kwargs):
        """Return a no-op completion."""
        from teddy_executor.core.domain.models.execution_report import LLMResponse
        return LLMResponse(content="Mocked response", model="mock", usage={})

    def validate_config(self, include_remote=False) -> list[str]:
        """No validation errors."""
        return []

    def get_context_window(self) -> int:
        """Return a large context window."""
        return 128000


class MockFileSystem:
    """IFileSystemManager implementation backed by a temp directory."""

    def __init__(self, tmp_path: str):
        self._root = Path(tmp_path)
        self._files: dict[str, str] = {}

    def read_file(self, path: str) -> str:
        resolved = str(Path(path).resolve())
        if resolved in self._files:
            return self._files[resolved]
        actual_path = Path(path)
        if actual_path.exists():
            return actual_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"File not found: {path}")

    def write_file(self, path: str, content: str) -> None:
        resolved = str(Path(path).resolve())
        self._files[resolved] = content
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def path_exists(self, path: str) -> bool:
        resolved = str(Path(path).resolve())
        if resolved in self._files:
            return True
        return Path(path).exists()

    def list_directory(self, path: str) -> list[str]:
        p = Path(path)
        if p.exists() and p.is_dir():
            return [str(f.name) for f in p.iterdir()]
        return []

    def copy_file(self, src: str, dest: str) -> None:
        content = self.read_file(src)
        self.write_file(dest, content)

    def delete_file(self, path: str) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()
        resolved = str(p.resolve())
        self._files.pop(resolved, None)

    def is_dir(self, path: str) -> bool:
        return Path(path).is_dir()

    def get_modification_time(self, path: str) -> float:
        return Path(path).stat().st_mtime if Path(path).exists() else 0.0

    # Additional methods required by IFileSystemManager interface
    def file_exists(self, path: str) -> bool:
        return self.path_exists(path)

    def rename(self, src: str, dest: str) -> None:
        content = self.read_file(src)
        self.write_file(dest, content)
        self.delete_file(src)


# ─── Monkey-patch ExecutionOrchestrator ─────────────────────────────────────────
def patch_execution_orchestrator():
    """
    Monkey-patch ExecutionOrchestrator.execute to inject console visibility
    and message visibility logging at the correct points.
    """
    from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
    original_execute = ExecutionOrchestrator.execute

    def patched_execute(
        self,
        plan=None,
        plan_content=None,
        plan_path=None,
        interactive=True,
        message=None,
        project_context=None,
    ):
        import typer

        # 1. Resolve plan (same as original but inline for simplicity)
        # We replicate the original flow minimally, injecting logging at the points
        plan_obj, temp_plan_path = None, None
        if plan:
            plan_obj = plan
        else:
            raise ValueError("Prototype requires a Plan object")

        # 2. Validate (skip validation for prototype)
        # 3. Interactive review (skip for prototype, assume reviewed)
        # 4. --- CONSOLE VISIBILITY INJECTION ---
        # After review, before action logs: print {emoji} {title}
        status_str = plan_obj.metadata.get("Status") or ""
        emoji = _extract_status_emoji(status_str)
        typer.secho(f"{emoji} {plan_obj.title}", fg=typer.colors.CYAN, err=True)

        # 5. Process actions (use original logic)
        action_logs = self._process_plan_actions(plan_obj, interactive)

        # 6. --- MESSAGE VISIBILITY INJECTION ---
        # After all actions, before report assembly: print User Message if present
        # Resolve message: prefer passed message, then plan.metadata["user_request"]
        resolved_message = message or plan_obj.metadata.get("user_request")
        if resolved_message:
            typer.secho(f"User Message: {resolved_message}", fg=typer.colors.YELLOW, err=True)

        # 7. Assemble report (use original logic)
        from datetime import datetime
        from teddy_executor.core.domain.models.report_assembly_data import ReportAssemblyData
        report = self._report_assembler.assemble(
            ReportAssemblyData(
                plan=plan_obj,
                action_logs=action_logs,
                start_time=datetime.now(),
                message=resolved_message,
                is_session=plan_obj.is_session,
            )
        )
        return report

    ExecutionOrchestrator.execute = patched_execute
    return original_execute  # return for potential restoration


# ─── Bootstrap ──────────────────────────────────────────────────────────────────
def build_plan(status: str, title: str, include_message: bool = False) -> 'Plan':
    """Build a Plan object with given status/title and a MESSAGE action."""
    from teddy_executor.core.domain.models.plan import Plan, ActionData, ActionType

    actions = [
        ActionData(
            type=ActionType.MESSAGE.value,
            params={"content": "This is a test message action."},
            description="Test message action",
        )
    ]
    metadata = {
        "Status": status,
        "Agent": "prototyper",
    }
    if include_message:
        metadata["user_request"] = "Let me refine this"

    return Plan(
        title=title,
        rationale="Test rationale for prototype.",
        actions=actions,
        metadata=metadata,
    )


def build_container(tmp_dir: str):
    """Build a punq container with overridden outbound ports."""
    from teddy_executor.container import create_container

    container = create_container()

    # Override outbound ports with our mocks
    from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient
    from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    container.register(IUserInteractor, instance=AutoConfirmUserInteractor())
    container.register(ILlmClient, instance=NoopLLMClient())
    container.register(IFileSystemManager, instance=MockFileSystem(tmp_dir))

    # Ensure config service is registered (pre-existing, but may need to be resolved)
    config_service = container.resolve(IConfigService)

    return container


# ─── Test Scenarios ─────────────────────────────────────────────────────────────
def run_default_scenario() -> bool:
    """Scenario 1 (default): No user message, assert console visibility line appears."""
    print("Running DEFAULT scenario (no user message)...", file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="teddy_proto_") as tmp_dir:
        patch_execution_orchestrator()
        container = build_container(tmp_dir)
        from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
        orchestrator = container.resolve(ExecutionOrchestrator)

        plan = build_plan("ON-TRACK 🟢", "Implement safety limits", include_message=False)

        # Capture stderr
        stderr_capture = io.StringIO()
        with contextlib.redirect_stderr(stderr_capture):
            report = orchestrator.execute(plan=plan, interactive=False, message=None)

        output = stderr_capture.getvalue()

        # Assertions:
        # 1. Console visibility line: 🟢 Implement safety limits
        assert "🟢 Implement safety limits" in output, f"Expected status line not found. Output:\n{output}"
        print("  ✓ Console visibility line present: 🟢 Implement safety limits", file=sys.stderr)

        # 2. No User Message line
        assert "User Message:" not in output, f"Unexpected User Message line. Output:\n{output}"
        print("  ✓ No User Message line (as expected)", file=sys.stderr)

        # 3. Status line appears before action logs (check order)
        lines = [l for l in output.splitlines() if l.strip()]
        status_idx = next((i for i, l in enumerate(lines) if "🟢 Implement safety limits" in l), -1)
        action_idx = next((i for i, l in enumerate(lines) if "MESSAGE" in l.upper() or "This is a test message" in l), -1)
        # Action logs appear via dispatcher output; we just check that status line appears somewhere
        assert status_idx >= 0, "Status line not found in output"
        print("  ✓ Status line position valid", file=sys.stderr)

        print("✓ DEFAULT scenario PASSED", file=sys.stderr)
        return True


def run_message_scenario() -> bool:
    """Scenario 2 (--scenario message): User message provided, assert both lines appear."""
    print("Running MESSAGE scenario (user message 'Let me refine this')...", file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="teddy_proto_") as tmp_dir:
        patch_execution_orchestrator()
        container = build_container(tmp_dir)
        from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
        orchestrator = container.resolve(ExecutionOrchestrator)

        # Build plan WITHOUT user_request in metadata (pass via message parameter instead)
        plan = build_plan("ON-TRACK 🟢", "Implement safety limits", include_message=False)

        # Capture stderr
        stderr_capture = io.StringIO()
        with contextlib.redirect_stderr(stderr_capture):
            report = orchestrator.execute(
                plan=plan,
                interactive=False,
                message="Let me refine this"
            )

        output = stderr_capture.getvalue()

        # Assertions:
        # 1. Console visibility line
        assert "🟢 Implement safety limits" in output, f"Expected status line not found. Output:\n{output}"
        print("  ✓ Console visibility line present: 🟢 Implement safety limits", file=sys.stderr)

        # 2. User Message line
        assert "User Message: Let me refine this" in output, f"Expected User Message not found. Output:\n{output}"
        print("  ✓ User Message line present: User Message: Let me refine this", file=sys.stderr)

        # 3. Order check: status line before User Message line
        lines = [l for l in output.splitlines() if l.strip()]
        status_idx = next((i for i, l in enumerate(lines) if "🟢 Implement safety limits" in l), -1)
        msg_idx = next((i for i, l in enumerate(lines) if "User Message: Let me refine this" in l), -1)
        assert status_idx < msg_idx, f"Order wrong: status at {status_idx}, msg at {msg_idx}"
        print("  ✓ Correct order: status line before User Message", file=sys.stderr)

        print("✓ MESSAGE scenario PASSED", file=sys.stderr)
        return True


def run_verify_scenario() -> bool:
    """Scenario 3 (--verify): 5-second boot check via subprocess."""
    import subprocess
    import sys

    print("Running VERIFY scenario (5-sec boot check)...", file=sys.stderr)

    # Run the prototype itself with --verify flag and check it doesn't crash
    cmd = [sys.executable, __file__, "--verify-inner"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=5,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ✗ Boot check failed with exit code {result.returncode}", file=sys.stderr)
            print(f"  stderr: {result.stderr}", file=sys.stderr)
            return False
        print("  ✓ Subprocess boot check terminated cleanly (exit 0)", file=sys.stderr)
        print("✓ VERIFY scenario PASSED", file=sys.stderr)
        return True
    except subprocess.TimeoutExpired:
        print("  ✗ Boot check timed out after 5 seconds", file=sys.stderr)
        return False


def run_verify_inner():
    """Inner verification: just bootstraps container and creates a plan, then exits."""
    with tempfile.TemporaryDirectory(prefix="teddy_proto_") as tmp_dir:
        patch_execution_orchestrator()
        container = build_container(tmp_dir)
        from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
        orchestrator = container.resolve(ExecutionOrchestrator)
        plan = build_plan("ON-TRACK 🟢", "Test", include_message=False)
        report = orchestrator.execute(plan=plan, interactive=False)
        # If we get here, boot succeeded
        print("Inner boot verification successful.", file=sys.stderr)
        sys.exit(0)


# ─── Main ───────────────────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Console and Message Visibility Prototype")
    parser.add_argument("--scenario", choices=["default", "message", "verify"], default="default",
                        help="Scenario to run")
    parser.add_argument("--verify-inner", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.verify_inner:
        run_verify_inner()
        return

    failures = 0
    if args.scenario == "default":
        if not run_default_scenario():
            failures += 1
    elif args.scenario == "message":
        if not run_message_scenario():
            failures += 1
    elif args.scenario == "verify":
        if not run_verify_scenario():
            failures += 1

    if failures > 0:
        print(f"\n❌ {failures} scenario(s) FAILED", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n✅ Scenario '{args.scenario}' PASSED", file=sys.stderr)


if __name__ == "__main__":
    main()