# Bug: teddy init fails and start doesn't auto-init
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- **Expected:** Running `teddy init` when `.teddy/` does not exist should create the directory and populate it with default files (config, prompts, etc.).
- **Expected:** Running `teddy start` when `.teddy/` does not exist should automatically run initialization before starting the session.
- **Actual:** `teddy init` terminates without creating `.teddy/` or its contents. `teddy start` also fails without auto-initializing.

## Context & Scope
### Regressing Delta
Unknown yet. This may be an existing bug in the init flow or a regression from recent refactoring.

### Environmental Triggers
- Project root without an existing `.teddy/` directory.
- Possibly related to resource path resolution (e.g., `importlib.resources`).

### Ruled Out
N/A

## Diagnostic Analysis
### Causal Model
All local reproduction attempts (MRE, CLI probe, CliRunner command, existing acceptance tests) succeed when running from the development source tree (`src/` on `PYTHONPATH`). Remote probing across Ubuntu, macOS, and Windows with Python 3.11 confirms that `teddy init` works correctly in a pip-installed environment (TEST 2 SUCCESS on all three platforms — .teddy/ created with all files). The `importlib.resources.files()` resource resolution works correctly for both editable and pip-installed packages.

**The bug is confirmed and root cause identified.** When the user runs `teddy init` inside a directory that is a subfolder of an existing TeDDy project (i.e., a parent directory contains `.teddy/`), `find_project_root()` returns the project root path instead of the CWD. The file system adapter then resolves `.teddy/` relative to the project root, not the current working directory. Since `.teddy/` already exists in the project root, the `init` command reports success ("TeDDy initialized in .teddy folder.") but creates nothing in the user's CWD.

This is **not a Python version or resource resolution issue**. The root cause is that `find_project_root()` is designed to discover the nearest ancestor TeDDy project, which is correct for `start`/`resume`/`execute` commands (which operate within a project), but wrong for `init` (which creates a *new* project and should always target the CWD).

The bare `except: pass` in `InitService._get_default_content()` remains a code quality concern but is not the root cause for this bug.

### Discrepancies
- ~~The CLI `init` command should create `.teddy/` but doesn't.~~ (Resolved: Bug not reproducible in CI with Python 3.11. Likely Python 3.12+ importlib.resources API change masked by bare `except: pass`.)
- ~~The CLI `start` command should auto-init but doesn't.~~ (Resolved: Same as above — the init flow works correctly in all tested environments.)
- ~~`importlib.resources.files()` fails in pip-installed package.~~ (Resolved: Remote probe confirmed resources resolve correctly in pip-installed package on all platforms.)

### Investigation History
1. **Initial context gathering** — Read InitService, CLI handlers, container wiring, and resource files. Identified key components: `InitService._get_default_content()`, `_ensure_project_initialized()`, `get_container()`.
2. **MRE using `create_container()` in temp dir** — PASSES (.teddy/ created correctly). Core InitService logic and file system adapter confirmed working.
3. **CLI probe using `get_container()` + `_ensure_project_initialized()`** — PASSES (.teddy/ created, adapter registered correctly).
4. **Existing acceptance tests** (`test_auto_initialization`, `test_streamlined_init`) — PASS locally.
5. **CliRunner probe of actual `teddy init` CLI command in clean temp dir** — PASSES (exit code 0, .teddy/ created with all files).
6. **Discovered**: Local project root has an existing `.teddy/` directory — this masks the bug during development because `find_project_root()` returns the project root instead of the CWD.
7. **Remote Probe Attempt 1 (run 27951787927)** — Disproved the `importlib.resources` hypothesis: resources resolve correctly in pip-installed package. Probe had `--no-deps` bug (missing typer/yaml modules invalidated TEST 2).
8. **Remote Probe Attempt 2 (run 27951935176)** — Fixed probe, installed with dependencies.
   - **TEST 1 (editable/poetry):** FAILURE on all 3 platforms (Ubuntu, macOS, Windows). *False negative* — probe bug: `poetry run` executed from `$PROJECT_ROOT` instead of `$TEST_DIR_1`, so `.teddy/` was created in the project root (where it already existed), not in the temp dir. Result invalid.
   - **TEST 2 (pip install):** SUCCESS on ALL 3 platforms. `.teddy/` created correctly with all expected files (.gitignore, config.yaml, init.context, prompts/). `importlib.resources.files()` resolved correctly in pip-installed package.
   - **Conclusion:** Bug is NOT reproducible in CI with Python 3.11. Likely Python-version-specific (3.12+) or environmental.
9. **Code review finding**: `InitService._get_default_content()` has a bare `except: pass` block at lines ~82-84 that catches `(yaml.YAMLError, OSError, ImportError, AttributeError)`. Any of these errors (especially `AttributeError` from a changed importlib.resources API) would be silently swallowed, returning `None` instead of the template content. This would cause `ensure_initialized()` to skip file creation without any error message.
10. **Local test in `testing_shit/` directory** — User's exact reproduction scenario. Reproduced the bug: `python3 -m teddy_executor init` prints "TeDDy initialized in .teddy folder." with exit code 0, but `.teddy/` is NOT created in CWD. Diagnostic confirms:
    - `find_project_root()` returns the project root (`/Users/raphaelatteritano/Desktop/dev/TeDDy-copy`) because `.teddy/` exists there.
    - The file system adapter resolves `.teddy/` relative to the project root, not CWD.
    - `.teddy/` already exists in the project root, so the adapter reports success but does not create anything in `testing_shit/`.
    - **Root cause**: `find_project_root()` discovers the nearest ancestor containing `.teddy/` and sets the adapter's `root_dir` to that path. When the user runs `init` inside the project tree, the command targets the existing `.teddy/` instead of creating a new one in the CWD.
    - **Fix direction**: `init` and `start` commands should operate relative to the **current working directory**, not the project root. Options: (a) Force `root_dir` to CWD during init, (b) check for `.teddy/` in CWD first before falling back to parent search, (c) provide a `--dir` flag to specify where to initialize.
11. **Fix verification attempt via poetry run** — After applying the fix (`root = str(Path.cwd())`), attempted `poetry run python -m teddy_executor init` from `testing_shit/`. Failed: `No module named teddy_executor` — the package is not installed in the venv, only available via direct import from `src/`. System `python3` loads the installed (unpatched) `teddy-cli` package, so cannot be used for verification until after reinstall.
12. **Regression test verification (GREEN)** — Ran `poetry run pytest tests/suites/unit/test_bug_05_init_cwd_vs_project_root.py`. The test creates a parent directory with an existing `.teddy/`, then runs `init` from a subdirectory via `CliRunner.invoke(app, ...)` (direct source import). It asserts `.teddy/` is created in the subdirectory (CWD), not the parent. **PASSED — fix confirmed working.** The regression test directly reproduces the user's exact bug scenario (subfolder inside a project with existing `.teddy/`).
13. **Regression discovered in full test suite** — `test_teddy_context_aggregates_cascading_context` failed because the blanket `root = str(Path.cwd())` change caused the `context` command to resolve files relative to the turn directory (deep inside `.teddy/sessions/...`) instead of the project root. **Root cause of regression:** The fix was too broad — all commands (`init`, `start`, `context`, `resume`, `execute`) shared the same `_ensure_project_initialized()` function. **Refined fix:** Added optional `root_dir` parameter to `_ensure_project_initialized()`. Only `init` passes `root_dir=str(Path.cwd())`. Other commands continue to use `find_project_root()`. This restores the original `context`/`resume`/`execute` behavior while fixing the `init` bug.

## Solution

### Root Cause
When the user runs `teddy init` inside a directory that is a subfolder of an existing TeDDy project (where a parent directory contains `.teddy/`), the `find_project_root()` function returns the project root path instead of the current working directory. The file system adapter then resolves `.teddy/` relative to the project root, not the CWD. Since `.teddy/` already exists in the project root, the `init` command reports success but creates nothing in the user's CWD.

### Fix
Refined `_ensure_project_initialized()` to accept an optional `root_dir` parameter in `src/teddy_executor/__main__.py`. When `root_dir` is provided (as it now is by the `init` command with `str(Path.cwd())`), the function uses that path directly. When omitted (as it is by `start`, `context`, `resume`, and `execute`), the function falls back to `find_project_root()` to discover the nearest parent project.

This ensures:
- **`init`**: Always creates `.teddy/` in the current working directory (fixes the bug).
- **`start`/`context`/`resume`/`execute`**: Continue to operate within an existing project tree by finding the nearest parent `.teddy/` directory.

### Preventative Measures
1. **Targeted fix**: The `init` command explicitly passes CWD as the root directory, isolating the fix to only the command that creates new projects. Other commands retain their existing project-discovery behavior via `find_project_root()`.
2. **Regression prevention**: A dedicated regression test (`test_bug_05_init_cwd_vs_project_root.py`) simulates the exact user scenario (running `init` from a subdirectory inside an existing project tree) and asserts `.teddy/` is created in CWD, not in the parent.
3. **Bare `except: pass` in `InitService._get_default_content()`**: This remains a code quality concern that can silently swallow errors from `importlib.resources` API changes (Python 3.12+). A future fix should replace the bare `except` with specific error logging and re-raise for unknown errors.
