#!/usr/bin/env python3
"""
Prototype: REAL teddy start with Tee history.log capture.

This is the end-to-end prototype the user requested. It:
1. Contains the full Tee class
2. PATCHES src/teddy_executor/core/utils/io.py (creates it if missing)
3. PATCHES src/teddy_executor/core/services/session_orchestrator.py to install Tee
4. RUNS a real 'teddy start -y' session (auto-approved, single turn)
5. DISPLAYS the generated history.log to the user
6. RESTORES all modified files, leaving src/ perfectly clean

Usage:
    poetry run python spikes/prototypes/00-25-history-log-real.py

Requires:
    - LLM API key in .teddy/config.yaml
    - poetry environment with all dependencies installed
"""

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, TextIO


# =============================================================================
# 1. Tee Implementation (to be inserted into src/)
# =============================================================================

TEE_CLASS_SOURCE = '''
import sys
from pathlib import Path
from typing import Optional, TextIO


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
            pass  # Swallow flush failure per spec

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
            self._log_file = None
            return self

        self._stdout_writer = _TeeWriter(self._original_stdout, self._log_file)
        self._stderr_writer = _TeeWriter(self._original_stderr, self._log_file)
        sys.stdout = self._stdout_writer
        sys.stderr = self._stderr_writer
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
'''


# =============================================================================
# 2. Patch Specifications
# =============================================================================

TEE_IMPORT_LINE = (
    '\nfrom teddy_executor.core.utils.io import Tee as _Tee\n'
)

# The Tee installation code to add after the `is_session` line in execute()
TEE_INSTALL_CODE = '''
        # Install Tee for history.log capture (session mode only)
        _tee = None
        if is_session and plan_path:
            try:
                _log_path = Path(plan_path).parent.parent / "history.log"
                _tee = _Tee(_log_path)
                _tee.__enter__()
            except Exception:
                _tee = None

'''


# =============================================================================
# 3. File Patching Helpers
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_IO_PATH = PROJECT_ROOT / "src" / "teddy_executor" / "core" / "utils" / "io.py"
SRC_ORCHESTRATOR_PATH = (
    PROJECT_ROOT / "src" / "teddy_executor" / "core" / "services" / "session_orchestrator.py"
)


def backup_file(path: Path) -> Optional[Path]:
    """Creates a .bak copy of the file. Returns backup path or None."""
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(str(path), str(bak))
    return bak


def restore_backup(backup_path: Optional[Path], original_path: Path) -> bool:
    """Restores a file from its backup. Returns True on success."""
    if backup_path and backup_path.exists():
        shutil.copy2(str(backup_path), str(original_path))
        backup_path.unlink()
        return True
    return False


def patch_orchestrator(file_path: Path) -> bool:
    """
    Edits session_orchestrator.py to:
    1. Add the Tee import
    2. Install Tee after is_session detection
    3. Wrap the core logic in try/finally to clean up Tee
    Returns True on success.
    """
    original = file_path.read_text(encoding="utf-8")

    # --- Step 1: Add Tee import ---
    # Insert after the last import from teddy_executor
    import_insert = (
        "from teddy_executor.core.services.session_replanner import SessionReplanner\n"
    )
    tee_import = (
        "\nfrom teddy_executor.core.utils.io import Tee as _Tee\n"
    )

    if tee_import in original:
        print("  ✓ Tee import already present")
        modified = original
    else:
        modified = original.replace(import_insert, import_insert + tee_import)
        print("  ✓ Added Tee import")

    # --- Step 2: Install Tee after is_session detection ---
    # Find the line: is_session = self._is_session_mode(plan_path)
    find_is_session = "        is_session = self._is_session_mode(plan_path)"
    tee_install = """        is_session = self._is_session_mode(plan_path)

        # Install Tee for history.log capture (session mode only)
        _tee = None
        if is_session and plan_path:
            try:
                _log_path = Path(plan_path).parent.parent / "history.log"
                _tee = _Tee(_log_path)
                _tee.__enter__()
            except Exception:
                _tee = None

"""

    old_install = """        is_session = self._is_session_mode(plan_path)

        # Install Tee for history.log capture (session mode only)
        _tee = None
        if is_session and plan_path:
            try:
                _log_path = Path(plan_path).parent.parent / "history.log"
                _tee = _Tee(_log_path)
                _tee.__enter__()
            except Exception:
                _tee = None

"""

    if tee_install in modified or old_install in modified:
        print("  ✓ Tee installation already present")
    else:
        modified = modified.replace(find_is_session, tee_install.rstrip("\n"))
        print("  ✓ Added Tee installation code")

    # --- Step 3: Wrap the core logic in try/finally to clean up Tee ---
    # We need to find the beginning of the main execution block and wrap it.
    # The code after Tee install and before the return statement needs a try/finally.
    #
    # Strategy: Find the line that starts the main block (after Tee install)
    # and wrap it with try/finally that cleans up _tee.
    #
    # The current structure after patch:
    #   is_session = ...
    #   [Tee install block]
    #   # 1. Resolve Plan
    #   result = self._prepare_plan_parsing(...)
    #
    # We need to add a try before "# 1. Resolve Plan" and a finally after the report return.
    # But this is complex because there are multiple return paths.
    #
    # SIMPLER APPROACH: Use a try/finally around the entire block after Tee install.
    # Inject it surgically.

    # Find the comment "# 1. Resolve Plan (Parse only)"
    resolve_plan_comment = "        # 1. Resolve Plan (Parse only)"
    try_block = f"""        try:
            # 1. Resolve Plan (Parse only)"""

    if "try:" in modified and resolve_plan_comment.replace(
        "        # 1.", "            # 1."
    ) in modified:
        print("  ✓ Try block already present")
    else:
        modified = modified.replace(resolve_plan_comment, try_block)
        print("  ✓ Added try block before execution logic")

    # Find the return statement and add finally before it
    # The last return in execute() is: return report
    # We need to find the proper indentation level
    find_return = "        return report"

    # Check if finally already added
    if "        finally:" in modified:
        print("  ✓ Finally block already present")
    else:
        # Insert finally block before the return statement
        finally_block = """        finally:
            if _tee is not None:
                try:
                    _tee.__exit__(None, None, None)
                except Exception:
                    pass
        return report"""
        modified = modified.replace(find_return, finally_block)
        print("  ✓ Added finally block for Tee cleanup")

    # --- Write modified file ---
    file_path.write_text(modified, encoding="utf-8")
    print("  ✓ Wrote patched session_orchestrator.py")
    return True


def patch_io_file(file_path: Path) -> bool:
    """
    Creates or updates src/teddy_executor/core/utils/io.py with the Tee class.
    Returns True on success.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        print("  ✓ io.py already exists, ensuring Tee class is present")
        content = file_path.read_text(encoding="utf-8")
        if "class Tee" in content:
            print("  ✓ Tee class already present in io.py")
            return True

    file_path.write_text(TEE_CLASS_SOURCE.lstrip("\n"), encoding="utf-8")
    print("  ✓ Created/updated io.py with Tee class")
    return True


def verify_patches() -> bool:
    """Verifies the patches were applied correctly."""
    # Check io.py
    io_content = SRC_IO_PATH.read_text(encoding="utf-8")
    if "class Tee" not in io_content:
        print("  ✗ Tee class not found in io.py")
        return False
    if "class _TeeWriter" not in io_content:
        print("  ✗ _TeeWriter class not found in io.py")
        return False
    print("  ✓ io.py verified")

    # Check orchestrator
    orch_content = SRC_ORCHESTRATOR_PATH.read_text(encoding="utf-8")
    if "from teddy_executor.core.utils.io import Tee as _Tee" not in orch_content:
        print("  ✗ Tee import not found in session_orchestrator.py")
        return False
    if "_tee = None" not in orch_content:
        print("  ✗ Tee installation not found in session_orchestrator.py")
        return False
    if "_tee.__enter__()" not in orch_content:
        print("  ✗ Tee __enter__ call not found in session_orchestrator.py")
        return False
    if "_tee.__exit__" not in orch_content:
        print("  ✗ Tee __exit__ call not found in session_orchestrator.py")
        return False
    print("  ✓ session_orchestrator.py verified")
    return True


# =============================================================================
# 4. Run teddy start and capture results
# =============================================================================

def run_teddy_session() -> dict:
    """
    Runs 'teddy start -a developer -m "Hello, test session" -y' as a subprocess.
    Returns a dict with:
      - success: bool
      - stdout: str
      - stderr: str
      - session_dir: str | None  (path to the generated session directory)
      - history_log_content: str | None
      - error: str | None
    """
    result = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "session_dir": None,
        "history_log_content": None,
        "error": None,
    }

    print("\n  Running 'teddy start -a developer -m \"Hello, test session\" -y'...")
    print("  (This will make a real LLM call — may take 10-30 seconds)\n")

    try:
        proc = subprocess.run(
            [
                "poetry", "run", "teddy", "start",
                "-a", "developer",
                "-m", "Hello, test session",
                "-y",
            ],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes for LLM call + execution
            cwd=str(PROJECT_ROOT),
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["success"] = proc.returncode == 0

        # Print output
        if proc.stdout:
            print(f"  STDOUT (last 50 lines):\n{proc.stdout[-2000:]}")
        if proc.stderr:
            print(f"  STDERR (last 50 lines):\n{proc.stderr[-2000:]}")
        print(f"  Exit code: {proc.returncode}")

    except subprocess.TimeoutExpired:
        result["error"] = "Timed out after 120 seconds"
        print(f"  ✗ {result['error']}")
        return result
    except FileNotFoundError:
        result["error"] = "poetry command not found. Is poetry installed?"
        print(f"  ✗ {result['error']}")
        return result
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ Error running teddy start: {e}")
        return result

    # --- Find the generated session directory ---
    sessions_dir = PROJECT_ROOT / ".teddy" / "sessions"
    if not sessions_dir.exists():
        result["error"] = "No .teddy/sessions/ directory found"
        print(f"  ✗ {result['error']}")
        return result

    # Find the most recently modified session
    session_dirs = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    if not session_dirs:
        result["error"] = "No session directories found"
        print(f"  ✗ {result['error']}")
        return result

    latest_session = session_dirs[0]
    result["session_dir"] = str(latest_session)
    print(f"  ✓ Latest session: {latest_session.name}")

    # --- Find history.log ---
    history_log = latest_session / "history.log"
    if history_log.exists():
        result["history_log_content"] = history_log.read_text(encoding="utf-8")
        print(f"  ✓ history.log found ({len(result['history_log_content'])} chars)")
    else:
        # Maybe it's in a subdirectory? Check turn dirs
        turn_dirs = sorted(
            [d for d in latest_session.iterdir() if d.is_dir() and d.name.isdigit()],
        )
        if turn_dirs:
            result["session_dir"] = str(turn_dirs[0].parent)
        result["error"] = "history.log not found in session directory"
        print(f"  ✗ {result['error']}")

    return result


# =============================================================================
# 5. Main Orchestration
# =============================================================================

def cleanup(bak_orch: Optional[Path], bak_io: Optional[Path], created_io: bool):
    """Restores all modified files."""
    print("\n  Cleaning up...")

    # Restore session_orchestrator.py
    if restore_backup(bak_orch, SRC_ORCHESTRATOR_PATH):
        print("  ✓ Restored session_orchestrator.py")
    elif bak_orch is None:
        print("  - No backup needed for session_orchestrator.py (file unchanged)")

    # If io.py was created (didn't exist before), delete it
    if created_io and SRC_IO_PATH.exists():
        try:
            SRC_IO_PATH.unlink()
            print("  ✓ Removed created io.py")
        except Exception as e:
            print(f"  ! Could not remove io.py: {e}")

    # If io.py existed before, restore from backup
    if bak_io and SRC_IO_PATH.exists():
        restore_backup(bak_io, SRC_IO_PATH)
        print("  ✓ Restored io.py from backup")


def main():
    print("=" * 60)
    print("  REAL tee'Ddy start — history.log Prototype")
    print("  This patches the real app, runs a session, and shows history.log")
    print("=" * 60)

    print("\n--- Step 1: Patch src/ files ---")

    # Backup files
    bak_orch = backup_file(SRC_ORCHESTRATOR_PATH)
    created_io = not SRC_IO_PATH.exists()
    bak_io = backup_file(SRC_IO_PATH)

    print(f"  Backed up session_orchestrator.py: {'yes' if bak_orch else 'no new file'}")
    print(f"  Backed up io.py: {'yes' if bak_io else 'no new file'}")

    # Apply patches
    try:
        io_ok = patch_io_file(SRC_IO_PATH)
        if not io_ok:
            print("  ✗ Failed to patch io.py")
            cleanup(bak_orch, bak_io, created_io)
            sys.exit(1)

        orch_ok = patch_orchestrator(SRC_ORCHESTRATOR_PATH)
        if not orch_ok:
            print("  ✗ Failed to patch session_orchestrator.py")
            cleanup(bak_orch, bak_io, created_io)
            sys.exit(1)

        # Verify
        print("\n--- Step 2: Verify patches ---")
        if not verify_patches():
            print("  ✗ Patch verification failed")
            cleanup(bak_orch, bak_io, created_io)
            sys.exit(1)

        # Run session
        print("\n--- Step 3: Run teddy start -y ---")
        result = run_teddy_session()

        # Show results
        print("\n--- Step 4: Results ---")
        if result["error"]:
            print(f"\n  ⚠ Error: {result['error']}")

        if result["history_log_content"]:
            print("\n  📄 Generated history.log:")
            print("-" * 50)
            print(result["history_log_content"])
            print("-" * 50)
        else:
            print("\n  ⚠ No history.log was generated.")
            print("  This may mean the session completed but the Tee was not installed correctly.")
            print("  Check stdout/stderr output above for clues.")

        if result["stdout"]:
            print("\n  Full stdout:")
            print(result["stdout"])

        if result["stderr"]:
            print("\n  Full stderr:")
            print(result["stderr"])

    except Exception as e:
        print(f"\n  ✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore everything
        print("\n--- Step 5: Cleanup (restoring original files) ---")
        cleanup(bak_orch, bak_io, created_io)

    # Verify cleanup
    print("\n--- Step 6: Verify cleanup ---")
    orch_content = SRC_ORCHESTRATOR_PATH.read_text(encoding="utf-8")
    if "_Tee" in orch_content or "_tee" in orch_content:
        print("  ✗ session_orchestrator.py still contains Tee references! Manual check needed.")
    else:
        print("  ✓ session_orchestrator.py clean (no Tee references)")

    if SRC_IO_PATH.exists() and not created_io:
        io_content = SRC_IO_PATH.read_text(encoding="utf-8")
        if "class Tee" in io_content and bak_io is not None:
            # Check if we restored correctly by comparing to original
            original = bak_io.read_text(encoding="utf-8") if bak_io else ""
            if io_content == original:
                print("  ✓ io.py restored to original")
            else:
                print("  ⚠ io.py may differ from original — check manually")
                if bak_io:
                    bak_io.unlink()
        elif "class Tee" not in io_content:
            print("  ✓ io.py unchanged (Tee not present — was not added)")
    elif not SRC_IO_PATH.exists():
        print("  ✓ io.py removed (did not exist before prototype)")

    print("\n" + "=" * 60)
    if result.get("history_log_content"):
        print("  ✅ SUCCESS: history.log was generated!")
        print(f"  Session directory: {result.get('session_dir', 'N/A')}")
    else:
        print("  ❌ history.log was NOT generated.")
        print("  Check the output above for clues.")
    print("=" * 60)


if __name__ == "__main__":
    main()