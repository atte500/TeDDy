#!/usr/bin/env bash
# Remote Probe: Test teddy init in both editable (poetry) and pip-installed environments.
set +e  # Do NOT exit on error – we capture failures gracefully
set -u   # Treat unset variables as errors

echo "=== Remote Probe: teddy init (pip-installed) ==="
echo "Python: $(python3 --version)"
echo "OS: $(uname -a)"
echo ""

# -------------------------------------------------------------------
# STEP 0: Locate project root (works both locally and in CI)
# -------------------------------------------------------------------
if [ -n "${GITHUB_WORKSPACE:-}" ]; then
    PROJECT_ROOT="$GITHUB_WORKSPACE"
else
    PROJECT_ROOT="$(cd "$(dirname "$0")" && cd ../../ && pwd)"
fi
echo "Project root: $PROJECT_ROOT"
echo "Package version: $(python3 -c 'import tomllib; print(tomllib.load(open("'$PROJECT_ROOT'/pyproject.toml","rb"))["project"]["version"])')"
echo ""

# -------------------------------------------------------------------
# STEP 1: Test editable install (poetry) – should work as baseline
# -------------------------------------------------------------------
echo "================= TEST 1: Editable (Poetry) ================="
TEST_DIR_1=$(mktemp -d)
echo "Test directory 1: $TEST_DIR_1"
cd "$TEST_DIR_1"
echo "Before:"
ls -la "$TEST_DIR_1/.teddy" 2>&1 || echo "  .teddy/ does not exist (expected)"

# Use poetry run to invoke the CLI from the project's venv (editable install)
cd "$PROJECT_ROOT"
poetry run python -m teddy_executor init 2>&1
INIT_EXIT=$?
cd "$TEST_DIR_1"

echo "init exit code: $INIT_EXIT"
if [ -d "$TEST_DIR_1/.teddy" ]; then
    echo "TEST 1 SUCCESS: .teddy/ created"
    echo "Contents: $(ls -A "$TEST_DIR_1/.teddy" 2>/dev/null)"
else
    echo "TEST 1 FAILURE: .teddy/ NOT created"
fi
echo ""

# Cleanup
rm -rf "$TEST_DIR_1"
cd "$PROJECT_ROOT"

# -------------------------------------------------------------------
# STEP 2: Test pip install (non-editable) – simulates user install
# -------------------------------------------------------------------
echo "================= TEST 2: Pip Install ================="
TEST_DIR_2=$(mktemp -d)
echo "Test directory 2: $TEST_DIR_2"

# Install the package into a temporary venv
python3 -m venv "$TEST_DIR_2/venv"
source "$TEST_DIR_2/venv/bin/activate"

# Install the package WITH dependencies (typer, pyyaml, etc. are required)
pip install "$PROJECT_ROOT" 2>&1
PIP_INSTALL_EXIT=$?
echo "pip install exit code: $PIP_INSTALL_EXIT"
echo ""

# Run teddy init in a subdirectory (outside the venv)
mkdir "$TEST_DIR_2/workdir"
cd "$TEST_DIR_2/workdir"
echo "Workdir: $PWD"
echo "Before:"
ls -la "$TEST_DIR_2/workdir/.teddy" 2>&1 || echo "  .teddy/ does not exist (expected)"

python -m teddy_executor init 2>&1
INIT_EXIT_2=$?
echo "init exit code: $INIT_EXIT_2"

if [ -d "$TEST_DIR_2/workdir/.teddy" ]; then
    echo "TEST 2 SUCCESS: .teddy/ created"
    echo "Contents:"
    ls -la "$TEST_DIR_2/workdir/.teddy"
    for f in .gitignore config.yaml init.context prompts; do
        if [ -e "$TEST_DIR_2/workdir/.teddy/$f" ]; then
            echo "  $f: EXISTS"
        else
            echo "  $f: MISSING"
        fi
    done
else
    echo "TEST 2 FAILURE: .teddy/ directory was NOT created!"
    echo ""
    echo "--- Diagnostic dump ---"
    echo "Package location:"
    python -c "import teddy_executor; print(teddy_executor.__file__)"
    echo ""
    echo "Resource check:"
    python -c "
from importlib import resources
try:
    p = resources.files('teddy_executor.resources.config')
    print(f'Resource path: {p}')
    print(f'Exists: {p.joinpath(\"config.yaml\").exists()}')
    try:
        files = list(p.iterdir())
        print(f'Files: {files}')
    except Exception as e:
        print(f'Error iterating dir: {e}')
except Exception as e:
    print(f'Error: {e}')
"
    echo ""
    echo "InitService direct check (using pip-installed code):"
    python -c "
import os
from teddy_executor.core.services.init_service import InitService
from teddy_executor.adapters.outbound.local_file_system_adapter import LocalFileSystemAdapter
from teddy_executor.core.services.edit_simulator import EditSimulator

srv = InitService(LocalFileSystemAdapter(EditSimulator()))
print(f'config_dir: {srv._config_dir}')
print(f'config_dir exists: {os.path.isdir(srv._config_dir) if srv._config_dir else \"N/A\"}')

# Try reading config templates
for name in ['config.yaml', 'init.context', '.gitignore']:
    content = srv._get_default_content(name)
    print(f'_get_default_content({name}): {content is not None}')
    if content:
        print(f'  preview: {content[:80]}')

# Try ensure_initialized
srv.ensure_initialized()
print(f'.teddy exists after direct call: {os.path.isdir(\".teddy\")}')
if os.path.isdir('.teddy'):
    import glob
    print(f'  contents: {os.listdir(\".teddy\")}')
"
fi

# Cleanup
deactivate 2>/dev/null || true
rm -rf "$TEST_DIR_2"
echo ""
echo "=== End of Remote Probe ==="

# Return non-zero if either test failed
if [ "$INIT_EXIT" -ne 0 ] || [ "$INIT_EXIT_2" -ne 0 ]; then
    exit 1
fi
exit 0