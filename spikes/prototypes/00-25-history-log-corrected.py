#!/usr/bin/env python3
"""
Patches session_orchestrator.py with correct indentation (method-body only),
runs teddy start -y, shows history.log, restores files.
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
    """Line-level insertion with method-boundary awareness."""
    lines = ORCHESTRATOR_PATH.read_text(encoding="utf-8").splitlines(keepends=True)

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

    # --- Step 3: Insert try: before # 1. Resolve Plan ---
    # Find the "# 1. Resolve Plan" line INSIDE execute() (not in other methods).
    # The correct line starts with 8 spaces then "# 1."
    resolve_idx = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("# 1. Resolve Plan") and line.startswith("        "):
            # Ensure this is not already indented inside a try block
            if not any("try:" in lines[max(0,i-5):i] for _ in [1]):
                resolve_idx = i
                break
    if resolve_idx is None:
        print("  ✗ Could not find '# 1. Resolve Plan'")
        return False

    # Find the end of execute() – the next `def ` at class level (0 or 4 spaces indent)
    execute_end_idx = None
    for i in range(resolve_idx + 1, len(lines)):
        if lines[i].startswith("    def ") and not lines[i].startswith("        def "):
            execute_end_idx = i
            break
    if execute_end_idx is None:
        print("  ✗ Could not find end of execute() method")
        return False

    # Check if try already present
    if any("try:" in lines[i] for i in range(resolve_idx - 3, resolve_idx)):
        print("  ✓ try block already present")
    else:
        # Insert try: before the resolve line
        lines.insert(resolve_idx, "        try:\n")
        # Adjust indices: resolve line is now at resolve_idx+1, execute_end shifted by 1
        resolve_idx += 1
        execute_end_idx += 1

        # Indent lines from resolve_idx (the original # 1. line, now shifted) to execute_end_idx - 1
        # by adding 4 spaces to all non-blank lines.
        for i in range(resolve_idx, execute_end_idx):
            line = lines[i]
            if line.strip() and not line.strip().startswith("#"):
                # Only indent if not already indented deeper (e.g., 12 spaces)
                # We want to add 4 spaces to the base indent (8 spaces) for the try body.
                # But we must be careful: lines already at 12 spaces should become 16.
                # Simplest: just add 4 spaces to every non-blank line in the range.
                lines[i] = "    " + line
        print("  ✓ Added try block and indented execute body")

    # --- Step 4: Add finally block before final return report ---
    # Find the last "        return report" within execute() (before execute_end_idx)
    final_return_idx = None
    for i in range(execute_end_idx - 1, resolve_idx - 1, -1):
        stripped = lines[i].strip()
        if stripped == "return report" and lines[i].startswith("            "):
            final_return_idx = i
            break
    if final_return_idx is None:
        # Fallback: find any return report within execute
        for i in range(execute_end_idx - 1, resolve_idx - 1, -1):
            if lines[i].strip() == "return report":
                final_return_idx = i
                break
    if final_return_idx is None:
        print("  ✗ Could not find return report line")
        return False

    # Check if finally already present
    if any("finally:" in lines[i] for i in range(final_return_idx - 6, final_return_idx)):
        print("  ✓ finally block already present")
    else:
        # The finally block must be at 8 spaces (same as try:) and come before the return.
        # But the return is currently indented at 12 or more spaces (inside try body).
        # We need to insert the finally at 8 spaces BEFORE the return line.
        # The return line is part of the try body, but we need to outdent the finally.
        # So we insert the finally lines at `final_return_idx` (before the return),
        # and the finally lines must be at 8 spaces.
        finally_block = [
            "        finally:\n",
            "            if _tee is not None:\n",
            "                try:\n",
            "                    _tee.__exit__(None, None, None)\n",
            "                except Exception:\n",
            "                    pass\n",
        ]
        # We need to remove the extra indentation from the return line because
        # the finally will be at 8 spaces and the return should be inside it.
        # Actually, the return line is currently part of the try body. We want:
        #   try:
        #       ...
        #       return report
        #   finally:
        #       ...
        # The return should stay inside try, and finally comes after.
        # So we find the current indentation of the return line (e.g., 12 spaces),
        # and we need to place finally at 8 spaces and the return remains inside finally.
        # But we cannot have a return inside finally followed by more code.
        # The correct structure is:
        #   try:
        #       ...
        #       return report    # inside try
        #   finally:
        #       ...
        # So we need to OUTDENT the return line back to 12 spaces (inside try),
        # then place finally after it at 8 spaces.
        # But the return line is already indented at 12+ spaces. We leave it as is.
        # We insert finally lines after the return line? No, finally must come before.
        # Actually in Python, finally comes after the try body and before any cleanup.
        # The try body ends at the last statement before finally.
        # So we need to:
        # 1. Take the return line out of the try body (outdent it) to 8 spaces.
        # 2. Insert finally after it.
        # But that changes the flow: the return would be outside try.
        # The correct pattern is:
        #   try:
        #       ...
        #       return report
        #   finally:
        #       ...
        # This is valid: the finally runs even after a return in try.
        # So we just need to insert finally at 8 spaces AFTER the return line,
        # but BEFORE any other code (like the next method).
        # Strategy: insert finally lines BEFORE the return line (at final_return_idx),
        # but outdent the return line to indicate it's inside try.
        # WAIT: the return line is already indented (12 spaces) inside try.
        # If we insert finally before it, the return remains inside try and finally comes after.
        # That's exactly right!
        for idx, fline in enumerate(finally_block):
            lines.insert(final_return_idx + idx, fline)
        print("  ✓ Added finally block for Tee cleanup")

    # Write the modified file
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
    print("  REAL teddy start → history.log (CORRECTED)")
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