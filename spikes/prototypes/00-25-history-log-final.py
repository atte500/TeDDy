#!/usr/bin/env python3
"""
Final prototype: patch session_orchestrator.py with correct indentation,
run teddy start -y, show history.log, restore files.
Method-boundary aware: only modifies lines inside execute().
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

# Tee class source (same as validated standalone prototype)
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
    IO_PY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if IO_PY_PATH.exists():
        print("  ✓ io.py already exists")
        return
    IO_PY_PATH.write_text(TEE_SOURCE, encoding="utf-8")
    print("  ✓ Created io.py with Tee class")


def patch_orchestrator():
    """Line-level insertion with method-boundary detection."""
    lines = ORCHESTRATOR_PATH.read_text(encoding="utf-8").splitlines(keepends=True)

    # Find method boundaries: execute() starts at "    def execute(" and ends at next "    def "
    execute_start_idx = None
    execute_end_idx = None
    for i, line in enumerate(lines):
        if line.startswith("    def execute("):
            execute_start_idx = i
        elif execute_start_idx is not None and line.startswith("    def ") and i > execute_start_idx:
            execute_end_idx = i
            break
    if execute_start_idx is None:
        print("  ✗ Could not find execute() method")
        return False
    if execute_end_idx is None:
        execute_end_idx = len(lines)  # fallback: end of file
    print(f"  ✓ execute() spans lines {execute_start_idx+1} to {execute_end_idx}")

    # --- Step 1: Add Tee import after SessionReplanner import ---
    import_line = "from teddy_executor.core.services.session_replanner import SessionReplanner\n"
    tee_import = "\nfrom teddy_executor.core.utils.io import Tee as _Tee\n"
    found_import = False
    for i, line in enumerate(lines):
        if import_line in line:
            found_import = True
            if any("from teddy_executor.core.utils.io import Tee as _Tee" in l for l in lines):
                print("  ✓ Tee import already present")
            else:
                lines.insert(i + 1, tee_import)
                execute_end_idx += 1  # shift due to insertion
                print("  ✓ Added Tee import")
            break
    if not found_import:
        print("  ✗ Could not find SessionReplanner import")
        return False

    # --- Step 2: Add Tee install block after is_session line ---
    is_session_line = "        is_session = self._is_session_mode(plan_path)\n"
    tee_install_block = """        is_session = self._is_session_mode(plan_path)

        # Install Tee for history.log capture
        _tee = None
        if is_session and plan_path:
            try:
                _log_path = Path(plan_path).parent.parent / "history.log"
                _tee = _Tee(_log_path)
                _tee.__enter__()
            except Exception:
                _tee = None

"""
    found_is_session = False
    for i, line in enumerate(lines):
        if line == is_session_line:
            found_is_session = True
            if any("Install Tee for history.log capture" in l for l in lines):
                print("  ✓ Tee install already present")
            else:
                lines[i] = tee_install_block
                print("  ✓ Added Tee install block")
            break
    if not found_is_session:
        print("  ✗ Could not find is_session line")
        return False

    # --- Step 3: Insert try: before # 1. Resolve Plan (inside execute) ---
    resolve_idx = None
    for i in range(execute_start_idx, execute_end_idx):
        stripped = lines[i].lstrip()
        if stripped.startswith("# 1. Resolve Plan") and lines[i].startswith("        "):
            # Ensure this is the FIRST occurrence (not inside a nested block)
            if not any("try:" in lines[max(0,i-5):i] for _ in [1]):
                resolve_idx = i
                break
    if resolve_idx is None:
        print("  ✗ Could not find '# 1. Resolve Plan'")
        return False

    # Check if try already present in the method body
    try_lines = [i for i in range(execute_start_idx, execute_end_idx) if lines[i].strip() == "try:"]
    if try_lines:
        print("  ✓ try block already present")
        # Use existing try line as resolve_idx
        resolve_idx = try_lines[0]
    else:
        # Insert try: before the resolve line
        lines.insert(resolve_idx, "        try:\n")
        execute_end_idx += 1
        # Now indent the body lines from resolve_idx+1 to execute_end_idx-1 by 4 spaces
        for i in range(resolve_idx + 1, execute_end_idx):
            line = lines[i]
            if line.strip() and not line.strip().startswith("finally:"):
                # Add 4 spaces to preserve relative indentation
                lines[i] = "    " + line
        print("  ✓ Added try block and indented execute body")

    # --- Step 4: Add finally block before next method, at 8 spaces ---
    # Find the last line that is part of the try body (before the next method)
    # The finally must be at 8 spaces (same as try:), and must be OUTSIDE the try body.
    # We need to outdent the last few lines? No, we just insert finally at 8 spaces
    # before the next method (execute_end_idx). The try body ends at the line before that.
    # But we also need to ensure the return report is inside try (12 spaces) and finally comes after.
    # The try body currently includes everything up to execute_end_idx-1.
    # We need to insert finally at execute_end_idx (before the next method) at 8 spaces.
    # However, the return reports might be inside the indented body. We need to check if there's a
    # "        finally:" already present in the method body.
    if any(lines[i].strip().startswith("finally:") for i in range(execute_start_idx, execute_end_idx)):
        print("  ✓ finally block already present")
    else:
        # Insert finally block at execute_end_idx (before next method) at 8 spaces
        finally_block = [
            "        finally:\n",
            "            if _tee is not None:\n",
            "                try:\n",
            "                    _tee.__exit__(None, None, None)\n",
            "                except Exception:\n",
            "                    pass\n",
        ]
        for idx, fline in enumerate(finally_block):
            lines.insert(execute_end_idx + idx, fline)
        print("  ✓ Added finally block for Tee cleanup")

    # Write modified file
    modified_text = "".join(lines)
    ORCHESTRATOR_PATH.write_text(modified_text, encoding="utf-8")

    # Verify syntax
    try:
        compile(modified_text, ORCHESTRATOR_PATH.name, "exec")
        print("  ✓ Syntax verification passed (compile() OK)")
    except SyntaxError as e:
        print(f"  ✗ Syntax error after patching: {e}")
        print(f"    Line {e.lineno}: {e.text}")
        bad_path = ORCHESTRATOR_PATH.with_suffix(".py.bad")
        ORCHESTRATOR_PATH.rename(bad_path)
        print(f"    Bad file saved to {bad_path}")
        return False

    print("  ✓ Wrote patched session_orchestrator.py")
    return True


def run_teddy_session():
    print("\n  Running 'teddy start -a developer -m \"Hello\" -y'...")
    print("  (This will make a real LLM call — may take 10-60 seconds)\n")
    try:
        result = subprocess.run(
            ["poetry", "run", "teddy", "start", "-a", "developer", "-m", "Hello", "-y"],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT),
        )
        print(f"  Exit code: {result.returncode}")
        if result.stdout:
            print(f"  STDOUT (last 1500 chars):\n{result.stdout[-1500:]}\n")
        if result.stderr:
            print(f"  STDERR (last 1500 chars):\n{result.stderr[-1500:]}\n")
        return result
    except subprocess.TimeoutExpired:
        print("  ✗ Timed out after 120 seconds")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def find_and_show_history_log():
    sessions_dir = PROJECT_ROOT / ".teddy" / "sessions"
    if not sessions_dir.exists():
        print("  ✗ No .teddy/sessions/ directory")
        return False
    session_dirs = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime, reverse=True,
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
    print("\n  Restoring original files...")
    subprocess.run(["git", "checkout", "src/teddy_executor/core/utils/io.py"],
                   cwd=str(PROJECT_ROOT), capture_output=True)
    subprocess.run(["git", "checkout", "src/teddy_executor/core/services/session_orchestrator.py"],
                   cwd=str(PROJECT_ROOT), capture_output=True)
    if IO_PY_PATH.exists():
        IO_PY_PATH.unlink()
    print("  ✓ Files restored")


def main():
    print("=" * 60)
    print("  REAL teddy start → history.log (FINAL)")
    print("  Method-boundary aware, no indentation corruption.")
    print("=" * 60)

    # Step 1: Create io.py
    print("\n--- Step 1: Create io.py ---")
    create_io_py()

    # Step 2: Patch orchestrator
    print("\n--- Step 2: Patch session_orchestrator.py ---")
    if not patch_orchestrator():
        restore_files()
        sys.exit(1)

    # Step 3: Verify patches (sanity)
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

    if success:
        print("\n  ✅ SUCCESS: history.log was generated!")
    else:
        print("\n  ❌ history.log was NOT generated.")
        print("  Check the output above for clues.")

    print("=" * 60)


if __name__ == "__main__":
    main()