#!/usr/bin/env bash
set -euo pipefail

# Remote probe: Check if launch_editor() has Windows-specific branching.
# We run a Python script that statically analyzes the source module.
python3 << 'PYEOF'
import sys, ast, pathlib

# Path to the target module relative to repo root
module_path = pathlib.Path("src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py")
if not module_path.exists():
    print("[ERROR] Module not found")
    sys.exit(1)

# Read the source code
source = module_path.read_text(encoding="utf-8")
tree = ast.parse(source)

# Check for any Windows-specific guard in the file
has_windows_guard = False
for node in ast.walk(tree):
    if isinstance(node, ast.If):
        # Look for comparisons like sys.platform == "win32" or platform.system() == "Windows"
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            comparators = node.test.comparators
            if isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name):
                if left.value.id == "sys" and left.attr == "platform":
                    for c in comparators:
                        if isinstance(c, ast.Constant) and c.value in ("win32", "win64"):
                            has_windows_guard = True
                if left.value.id == "platform" and left.attr == "system":
                    for c in comparators:
                        if isinstance(c, ast.Constant) and c.value == "Windows":
                            has_windows_guard = True
        # Also check for os.name == 'nt'
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            comparators = node.test.comparators
            if isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name):
                if left.value.id == "os" and left.attr == "name":
                    for c in comparators:
                        if isinstance(c, ast.Constant) and c.value == "nt":
                            has_windows_guard = True

# Also check all function definitions for the presence of "win32" or "nt" or "CREATE_NO_WINDOW" in the source
if not has_windows_guard:
    # broad string checks
    if "win32" in source or "win64" in source or "nt" in source or "CREATE_NO_WINDOW" in source or "os.startfile" in source or "startfile" in source:
        has_windows_guard = True

if has_windows_guard:
    print("WINDOWS PLATFORM HANDLING PRESENT")
    sys.exit(0)
else:
    print("WINDOWS PLATFORM HANDLING MISSING")
    sys.exit(1)
PYEOF