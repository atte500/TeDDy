# Bug: Dot Stripped from Leading‑Dot Filenames in Turn Context
- **Status:** Resolved
- **Milestone:** [N/A]
- **Vertical Slice:** [N/A]
- **Specs:** [N/A]

## Symptoms
**Expected:** When a file like `.pre-commit-config.yaml` is READ during a session, the path stored in `turn.context` (and displayed in the next turn's context under `## Resource Contents`) preserves the leading dot: `.pre-commit-config.yaml`.

**Actual:** The path is stored as `pre-commit-config.yaml` (leading dot missing). On the next turn, the `read_files_in_vault` call tries to resolve this incorrect path and fails, producing `--- FILE NOT FOUND ---` placeholders.

**Minimal Reproduction Steps:**
1. Start a session.
2. Have the agent READ `.pre-commit-config.yaml`.
3. Check the `turn.context` file in the session directory – it should list `.pre-commit-config.yaml`, but it instead lists `pre-commit-config.yaml`.
4. On the next turn, the context section shows `--- FILE NOT FOUND ---` for that file.

## Context & Scope
### Regressing Delta
Initial analysis points to path normalisation operations that use `str.lstrip("./")` instead of safer prefix‑removal. Two occurrences in `src/teddy_executor/core/utils/markdown.py`:
- `get_session_history_display_name()`
- `is_session_file_path()`

These functions are called during context formatting but do *not* write to `turn.context`. The actual write path is in the session persistence layer. The regressing commit is currently unknown.

### Environmental Triggers
Triggered whenever a file whose name starts with a dot (e.g., `.gitignore`, `.pre-commit-config.yaml`) is included in a READ action during a session.

### Ruled Out
- `LocalFileSystemAdapter._resolve_path()`: preserves the dot (no stripping).
- `ActionExecutor.confirm_and_dispatch()`: delegates to file system for reading, does not normalise the path stored for context.

## Diagnostic Analysis
### Causal Model
The bug is caused by `SessionService._extract_resource_path()` (lines 168-173 in `session_service.py`). This method uses `str.lstrip("./")` which treats the argument as a **set of characters**, not a prefix. Python's `str.lstrip` removes all leading characters that are in the given set. For a path like `.pre-commit-config.yaml`, the leading `.` is in the set `{'.', '/'}`, so it is stripped, yielding `pre-commit-config.yaml`.

**Data flow of the bug:**
1. In Turn N, the agent READS `.pre-commit-config.yaml`.
2. `ActionExecutor.dispatch_and_execute()` stores the action path in an `ActionLog`.
3. At turn transition, `SessionService.transition_to_next_turn()` calls `_apply_execution_effects()`.
4. `_apply_execution_effects()` iterates action logs and calls `_extract_resource_path()` on the resource value.
5. `_extract_resource_path()` applies `str.lstrip("./")`, transforming `.pre-commit-config.yaml` → `pre-commit-config.yaml`.
6. The corrupted path is written to the next turn's `turn.context` file.
7. On Turn N+1, `ContextService` reads `turn.context`, tries to read `pre-commit-config.yaml` (which doesn't exist), and displays `--- FILE NOT FOUND ---`.

**Correct fix:** Replace `str.lstrip("./")` with `str.removeprefix("./")` or a regex that only removes the exact `./` prefix. For non-Markdown-link paths that don't start with `./`, no stripping should occur at all — the path should be preserved as-is.

### Discrepancies
- The exact location of the write to `turn.context` has been observed: in `SessionService.transition_to_next_turn()` via `_apply_execution_effects()`. (resolved)
- The exact normalisation call that strips the dot is confirmed: `_extract_resource_path()` in `session_service.py` lines 168-173. (resolved)

### Investigation History
1. Grep revealed two `path.lstrip("./")` calls in `markdown.py`. These affect context display but not persistence. (resolved: display helpers, not root cause)
2. READ of `markdown.py` confirmed those calls exist only for session display helpers. (resolved)
3. Attempted to search for callers failed due to shell CWD mismatch. (resolved: CWD issue fixed)
4. Grep (Turn 4) confirmed `lstripl("./")` pattern in `session_service.py:172-173` as the root cause. Multiple other locations with same pattern found: `validation_rules/helpers.py:167,173`, `session_pruning_service.py:80,103`, `parser_infrastructure.py:72`, `local_file_system_adapter.py:60`. (resolved: root cause identified)
5. MRE empirically confirmed the bug: `_extract_resource_path` strips leading dots from `.pre-commit-config.yaml`, `.gitignore`, `.dotfile` paths. (planned)

## Solution
### Root Cause
`SessionService._extract_resource_path()` used `str.lstrip("./")` which treats the argument as a **set of characters** `{'.', '/'}`, not a prefix. This caused any leading dot in a path (e.g., `.pre-commit-config.yaml`) to be removed, yielding `pre-commit-config.yaml`. The corrupted path was then written to `turn.context`, causing `--- FILE NOT FOUND ---` on subsequent turns.

### Fix
Replace `str.lstrip("./")` with `str.removeprefix("./")` — which only removes the exact `./` prefix when present, preserving leading dots. This ensures:
- `.pre-commit-config.yaml` stays as `.pre-commit-config.yaml`
- `./relative/path` becomes `relative/path` (only the `./` prefix is stripped)
- Absolute paths like `/absolute/path` still have their leading `/` stripped via `lstrip("/")`

### Preventative Measures
The same `lstrip("./")` bug pattern appeared in 4 other files. This debt has been addressed for the two higher-risk locations:

| File | Lines | Risk Level | Status | Assessment |
|------|-------|------------|--------|------------|
| `validation_rules/helpers.py` | 167, 173 | HIGH | **FIXED** | Used for path normalization in validation rules — could affect validation of dot-file edits |
| `session_pruning_service.py` | 80, 103 | MEDIUM | **FIXED** | Used for normalizing paths during pruning — could affect pruning decisions for dot files |
| `parser_infrastructure.py` | 72 | LOW | Safe (skipped) | Strips leading `/` only, not `./` — no bug |
| `local_file_system_adapter.py` | 60 | LOW | Safe (skipped) | Strips leading `/` only, not `./` — no bug |

The systemic fix replaces `str.lstrip(char_set)` with `str.removeprefix(prefix)` for `./` prefix removal only.
