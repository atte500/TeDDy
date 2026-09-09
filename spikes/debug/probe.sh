#!/usr/bin/env bash
set -euo pipefail

# Remote probe: Check if launch_editor() has Windows-specific branching.
# We parse the AST and inspect only the launch_editor function body.
python3 << 'PYEOF'
import sys, ast, pathlib

module_path = pathlib.Path("src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py")
if not module_path.exists():
    print("[ERROR] Module not found")
    sys.exit(1)

source = module_path.read_text(encoding="utf-8")
tree = ast.parse(source)

# Find the launch_editor function node
launch_fn = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "launch_editor":
        launch_fn = node
        break

if not launch_fn:
    print("[ERROR] launch_editor function not found")
    sys.exit(1)

# Search for any Windows platform check within just this function
has_windows_guard = False

for node in ast.walk(launch_fn):
    if isinstance(node, ast.If):
        test = node.test
        # Check patterns: sys.platform == "win32", platform.system() == "Windows", os.name == "nt"
        if isinstance(test, ast.Compare) and len(test.comparators) == 1:
            left = test.left
            right = test.comparators[0]
            if isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name):
                if left.value.id == "sys" and left.attr == "platform":
                    if isinstance(right, ast.Constant) and right.value in ("win32", "win64"):
                        has_windows_guard = True
                if left.value.id == "platform" and left.attr == "system":
                    if isinstance(right, ast.Constant) and right.value == "Windows":
                        has_windows_guard = True
                if left.value.id == "os" and left.attr == "name":
                    if isinstance(right, ast.Constant) and right.value == "nt":
                        has_windows_guard = True
        # Also check simple constant True/False?
    # Check for subprocess creation flags like CREATE_NO_WINDOW
    if isinstance(node, ast.Attribute) and node.attr == "CREATE_NO_WINDOW":
        has_windows_guard = True

if has_windows_guard:
    print("WINDOWS PLATFORM HANDLING PRESENT")
    sys.exit(0)
else:
    print("WINDOWS PLATFORM HANDLING MISSING")
    sys.exit(1)
PYEOF
