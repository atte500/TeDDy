#!/usr/bin/env python3
"""
Run real teddy start with Tee, show history.log, then restore.

Safe: creates io.py, surgically patches session_orchestrator.py,
runs one auto-approved turn, displays history.log, then restores.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

IO_PY_PATH = PROJECT_ROOT / "src" / "teddy_executor" / "core" / "utils" / "io.py"
ORCHESTRATOR_PATH = (
    PROJECT_ROOT
    / "src"
    / "teddy_executor"
    / "core"
    / "services"
    / "session_orchestrator.py"
)

# ----- 1. Tee class source -----
TEE_SOURCE = """import sys
from pathlib import Path
from typing import Optional, TextIO


class _TeeWriter:
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
    def __init__(self, log_path: Path):
        self._log_path = log_path
        self._log_file: Optional[TextIO] = None
        self._original_stdout: Optional[TextIO] = None
        self._original_stderr: Optional[TextIO] = None

    def __enter__(self) -> "Tee":
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self._log_path, "a", encoding="utf-8")
        except OSError:
            return self
        sys.stdout = _TeeWriter(self._original_stdout, self._log_file)
        sys.stderr = _TeeWriter(self._original_stderr, self._log_file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
        if self._original_stderr is not None:
            sys.stderr = self._original_stderr
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
"""


def create_io_py():
    """Create the io.py file with the Tee class."""
    IO_PY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if IO_PY_PATH.exists():
        print("  ✓ io.py already exists, not overwriting")
        return
    IO_PY_PATH.write_text(TEE_SOURCE, encoding="utf-8")
    print("  ✓ Created io.py with Tee class")


def patch_orchestrator():
    """Surgically insert Tee install and try/finally into session_orchestrator.py."""
    original = ORCHESTRATOR_PATH.read_text(encoding="utf-8")

    # Step 1: Add Tee import after SessionReplanner import
    import_line = (
        "from teddy_executor.core.services.session_replanner import SessionReplanner"
    )
    if "from teddy_executor.core.utils.io import Tee as _Tee" in original:
        print("  ✓ Tee import already present")
    else:
        modified = original.replace(
            import_line,
            import_line + "\nfrom teddy_executor.core.utils.io import Tee as _Tee",
        )
        print("  ✓ Added Tee import")

    # Step 2: Add Tee install after is_session line
    is_session_line = "        is_session = self._is_session_mode(plan_path)"
    tee_install_block = (
        "        is_session = self._is_session_mode(plan_path)\n"
        "\n"
        "        # Install Tee for history.log capture\n"
        "        _tee = None\n"
        "        if is_session and plan_path:\n"
        "            try:\n"
        '                _log_path = Path(plan_path).parent.parent / "history.log"\n'
        "                _tee = _Tee(_log_path)\n"
        "                _tee.__enter__()\n"
        "            except Exception:\n"
        "                _tee = None\n"
    )
    if "_tee = None" in modified:
        print("  ✓ Tee install already present")
    else:
        modified = modified.replace(is_session_line, tee_install_block)
        print("  ✓ Added Tee install block")

    # Step 3: Add try before "# 1. Resolve Plan" and finally before "return report"
    resolve_plan_comment = "        # 1. Resolve Plan (Parse only)"
    try_block = (
        "        try:\n"
        "            # 1. Resolve Plan (Parse only)"
    )
    if "        try:" in modified and "            # 1. Resolve Plan" in modified:
        print("  ✓ try block already present")
    else:
        modified = modified.replace(resolve_plan_comment, try_block)
        print("  ✓ Added try before execution logic")

    # Add finally block before the final return report line
    return_line = "        return report"
    # We need to add a finally block that closes the Tee if it's active.
    # The code after the try block ends at the return. We insert a finally before that return.
    # To avoid adding finally to multiple returns, we'll only do it for the LAST return.
    # Find all occurrences of the exact line, and only replace the last one.
    lines = modified.splitlines(keepends=True)
    # Find line index of "        return report" (the last one)
    last_return_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == return_line:
            last_return_idx = i
    if last_return_idx is not None:
        # Check if finally already present before this return
        if last_return_idx >= 1 and "finally:" in lines[last_return_idx - 4]:
            print("  ✓ finally block already present")
        else:
            # Insert finally block just before the return line
            finally_block = [
                "        finally:\n",
                "            if _tee is not None:\n",
                "                try:\n",
                "                    _tee.__exit__(None, None, None)\n",
                "                except Exception:\n",
                "                    pass\n",
            ]
            lines[last_return_idx:last_return_idx] = finally_block
            modified = "".join(lines)
            print("  ✓ Added finally block for Tee cleanup")
    else:
        print("  ✗ Could not find 'return report' line")
        return False

    ORCHESTRATOR_PATH.write_text(modified, encoding="utf-8")
    print("  ✓ Wrote patched session_orchestrator.py")
    return True


def run_teddy_session():
    """Run teddy start -y as subprocess."""
    print("\n  Running 'teddy start -a developer -m \"Hello\" -y'...")
    print("  (This will make a real LLM call — may take 10-60 seconds)\n")
    try:
        result = subprocess.run(
            [
                "poetry",
                "run",
                "teddy",
                "start",
                "-a",
                "developer",
                "-m",
                "Hello",
                "-y",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        print(f"  Exit code: {result.returncode}")
        if result.stdout:
            print(f"  STDOUT (last 1000 chars):\n{result.stdout[-1000:]}\n")
        if result.stderr:
            print(f"  STDERR (last 1000 chars):\n{result.stderr[-1000:]}\n")
        return result
    except subprocess.TimeoutExpired:
        print("  ✗ Timed out after 120 seconds")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def find_and_show_history_log():
    """Find the most recent session and show history.log."""
    sessions_dir = PROJECT_ROOT / ".teddy" / "sessions"
    if not sessions_dir.exists():
        print("  ✗ No .teddy/sessions/ directory")
        return False
    session_dirs = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not session_dirs:
        print("  ✗ No session directories found")
        return False
    latest = session_dirs[0]
    history_log = latest / "history.log"
    if history_log.exists():
        content = history_log.read_text(encoding="utf-8")
        print(f"\n  ✓ history.log found at {history_log}")
        print(f"  Content ({len(content)} chars):\n")
        print("=" * 60)
        print(content)
        print("=" * 60)
        return True
    else:
        print(f"  ✗ No history.log found in {latest}")
        print("  Session directory contents:")
        for item in sorted(latest.iterdir()):
            t = "DIR" if item.is_dir() else "FILE"
            s = item.stat().st_size if item.is_file() else ""
            print(f"    [{t}] {item.name} {s}")
        return False


def restore_files():
    """Revert all changes to src/ via git checkout."""
    print("\n  Restoring original files...")
    subprocess.run(
        ["git", "checkout", "src/teddy_executor/core/utils/io.py"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "src/teddy_executor/core/services/session_orchestrator.py"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
    )
    # Remove io.py if it was newly created (git checkout won't delete untracked)
    if IO_PY_PATH.exists():
        IO_PY_PATH.unlink()
    print("  ✓ Files restored")


def main():
    print("=" * 60)
    print("  REAL teddy start → history.log Demo")
    print("  Patches src/, runs session, shows log, restores.")
    print("=" * 60)

    # Step 1: Create io.py
    print("\n--- Step 1: Create io.py ---")
    create_io_py()

    # Step 2: Patch orchestrator
    print("\n--- Step 2: Patch session_orchestrator.py ---")
    if not patch_orchestrator():
        restore_files()
        sys.exit(1)

    # Step 3: Verify patch (quick sanity)
    print("\n--- Step 3: Verify patches ---")
    orch = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
    checks = all(
        marker in orch
        for marker in [
            "from teddy_executor.core.utils.io import Tee as _Tee",
            "_tee = None",
            "_tee.__enter__()",
            "_tee.__exit__",
        ]
    )
    print(f"  {'✓' if checks else '✗'} Patches verified")

    # Step 4: Run teddy start
    print("\n--- Step 4: Run teddy start -y ---")
    result = run_teddy_session()

    # Step 5: Show history.log
    print("\n--- Step 5: Show history.log ---")
    success = find_and_show_history_log()

    # Step 6: Restore
    print("\n--- Step 6: Restore original files ---")
    restore_files()

    # Final
    if success:
        print("\n  ✅ SUCCESS: history.log was generated!")
    else:
        print("\n  ❌ history.log was NOT generated.")
        print("  Check the output above for clues.")

    print("=" * 60)


if __name__ == "__main__":
    main()