#!/usr/bin/env python3
"""
Prototype: REAL teddy start with Tee — history.log generation.

This prototype uses RUNTIME MONKEY-PATCHING to inject the Tee into
SessionOrchestrator.execute(). No source files are modified.

Usage:
    poetry run python spikes/prototypes/00-25-history-log-live.py

Requires:
    - LLM API key in .teddy/config.yaml
    - poetry environment
"""

import os
import sys
from pathlib import Path
from typing import Optional, TextIO

# Ensure we're in the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)


# =============================================================================
# 1. Tee Implementation (exactly as designed for src/)
# =============================================================================

class _TeeWriter:
    """Proxy writer that duplicates writes to an original stream and a log file."""

    def __init__(self, original: TextIO, log_file: TextIO):
        self._original = original
        self._log_file = log_file

    def write(self, text: str) -> None:
        self._original.write(text)
        self._original.flush()
        self._log_file.write(text)
        self._log_file.flush()

    def flush(self) -> None:
        self._original.flush()
        try:
            self._log_file.flush()
        except OSError:
            pass

    def isatty(self) -> bool:
        return self._original.isatty()

    @property
    def encoding(self) -> str:
        return self._original.encoding or "utf-8"


class Tee:
    """
    Context manager that replaces sys.stdout and sys.stderr with proxy writers
    that duplicate output to a log file.
    """

    def __init__(self, log_path: Path):
        self._log_path = log_path
        self._log_file: Optional[TextIO] = None
        self._original_stdout: Optional[TextIO] = None
        self._original_stderr: Optional[TextIO] = None
        self._stdout_writer: Optional[_TeeWriter] = None
        self._stderr_writer: Optional[_TeeWriter] = None

    def __enter__(self) -> "Tee":
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self._log_path, "a", encoding="utf-8")
        except OSError:
            # File open failure -> gracefully skip tee'ing
            self._log_file = None
            return self

        self._stdout_writer = _TeeWriter(self._original_stdout, self._log_file)
        self._stderr_writer = _TeeWriter(self._original_stderr, self._log_file)
        sys.stdout = self._stdout_writer
        sys.stderr = self._stderr_writer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Restore original streams first (critical for exception safety)
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
        if self._original_stderr is not None:
            sys.stderr = self._original_stderr

        # Close log file (swallow OSError per spec)
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass


# =============================================================================
# 2. Monkey-patch SessionOrchestrator.execute
# =============================================================================

def patch_orchestrator():
    """
    Monkey-patches SessionOrchestrator.execute to wrap the original call
    with a Tee context manager for history.log capture.
    """
    # Import lazily to ensure module is loaded after Tee is defined
    from teddy_executor.core.services import session_orchestrator as orch_module

    original_execute = orch_module.SessionOrchestrator.execute

    def patched_execute(self, plan=None, plan_content=None, plan_path=None,
                        interactive=True, message=None, project_context=None):
        """
        Wraps SessionOrchestrator.execute with Tee for history.log capture.
        """
        # Determine if session mode (same logic as _is_session_mode)
        is_session = False
        if plan_path:
            meta_path = Path(plan_path).parent / "meta.yaml"
            is_session = meta_path.exists()

        # Install Tee if session mode
        tee = None
        if is_session:
            try:
                log_path = Path(plan_path).parent.parent / "history.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                tee = Tee(log_path)
                tee.__enter__()
            except Exception:
                # If Tee fails, session continues without history.log
                tee = None

        try:
            return original_execute(self, plan=plan, plan_content=plan_content,
                                    plan_path=plan_path, interactive=interactive,
                                    message=message, project_context=project_context)
        finally:
            if tee:
                try:
                    tee.__exit__(None, None, None)
                except Exception:
                    pass

    # Apply the patch to the CLASS (affects all current and future instances)
    orch_module.SessionOrchestrator.execute = patched_execute
    print("  ✓ SessionOrchestrator.execute monkey-patched successfully")


# =============================================================================
# 3. Main: Patch + Run + Show
# =============================================================================

def main():
    print("=" * 60)
    print("  REAL teddy start — history.log Generation Demo")
    print("  Uses runtime monkey-patching — no source files modified.")
    print("=" * 60)

    # Step 1: Apply monkey-patch
    print("\n--- Step 1: Apply patch ---")
    patch_orchestrator()

    # Step 2: Run the CLI in-process
    # We need to set sys.argv so typer parses our command
    print("\n--- Step 2: Run 'teddy start -a developer -m \"Say hello\" -y' ---")
    print("  (This will make a real LLM call — may take 10-30 seconds)\n")

    # Save original sys.argv and restore after
    original_argv = sys.argv
    try:
        sys.argv = ["teddy", "start", "-a", "developer", "-m", "Say hello and list project files", "-y"]

        # Now import and run the CLI app
        from teddy_executor.__main__ import app

        try:
            app()
        except SystemExit:
            # Typer uses sys.exit() — catch it gracefully
            pass

    finally:
        sys.argv = original_argv

    # Step 3: Find and display the generated history.log
    print("\n--- Step 3: Find and display history.log ---")

    sessions_dir = PROJECT_ROOT / ".teddy" / "sessions"
    if not sessions_dir.exists():
        print("  ✗ No .teddy/sessions/ directory found")
        return

    # Find most recent session
    session_dirs = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    if not session_dirs:
        print("  ✗ No session directories found")
        return

    latest = session_dirs[0]
    print(f"  Latest session: {latest.name}")

    # Find history.log
    history_log = latest / "history.log"
    if history_log.exists():
        content = history_log.read_text(encoding="utf-8")
        print(f"  ✓ history.log found ({len(content)} chars)\n")
        print("=" * 60)
        print(content)
        print("=" * 60)
        print(f"  File: {history_log}")
    else:
        print(f"  ✗ No history.log found in {latest}")
        print("  Session directory contents:")
        for item in sorted(latest.iterdir()):
            item_type = "DIR" if item.is_dir() else "FILE"
            size = item.stat().st_size if item.is_file() else ""
            print(f"    [{item_type}] {item.name} {size}")


if __name__ == "__main__":
    main()