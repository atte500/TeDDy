# Bug: editor value persisted as absolute path; tilde paths rejected

- **Status:** Resolved
- **Milestone:** [03-foundational-refactors.md](/docs/project/milestones/03-foundational-refactors.md)
- **Vertical Slice:** [03-01-editor-validation-and-discovery.md](/docs/project/slices/03-01-editor-validation-and-discovery.md)
- **Specs:** [editor-validation-and-discovery.md](/docs/project/specs/editor-validation-and-discovery.md)

## Symptoms

Reported by the user immediately after the `editor`-write fix (Bug 63):

1. **Non-portable persisted value.** Selecting an editor from the discovery prompt writes the resolved ABSOLUTE path — e.g. `editor: /opt/homebrew/bin/codium` — into `.teddy/config.yaml`. The README documents the basename convention (`editor: "nvim"`, "any editor available on your `PATH`"), and an absolute path is machine-specific (the Homebrew prefix differs between Intel `/usr/local/bin` and Apple-Silicon `/opt/homebrew/bin`), so it does not travel with a copied config.
2. **Tilde paths rejected.** A custom editor command pointing at a personal binary via a tilde path — e.g. `~/bin/myeditor` — is rejected with `'~/bin/myeditor' was not found in PATH.` and the prompt loops, because no tilde expansion occurs before the PATH lookup.

**Minimal reproduction:** `spikes/debug/64-editor-value-probe.py` (Turn 28 evidence probe). Q1b showed the round-trip writes `editor: /opt/homebrew/bin/codium`; Q2 showed `_resolve_editor_cmd('~/bin/myeditor')` returned `None`. The PERMANENT guard is now the regression test `tests/suites/unit/adapters/inbound/test_editor_value_persistence.py`.

```shell
uv run python spikes/debug/64-editor-value-probe.py
```

## Context & Scope

### Regressing Delta

Both behaviours are original to Slice 03-01 (`editor-validation-and-discovery`); they are design gaps in the initial implementation, not regressions.

- **Basename vs path:** `_prompt_for_editor_selection` (`session_cli_handlers.py`) persists `available[index - 1][1]` — the second element of the `(basename, resolved_path)` tuple returned by `ConsoleToolingHelper.discover_editors()`, i.e. the resolved absolute path. Spec §4 explicitly mandates this ("persist the selected editor's resolved absolute path to config"), so the code matches the spec; both diverge from the README.
- **Tilde:** `ConsoleToolingHelper._resolve_editor_cmd` (`console_tooling.py`) does `shlex.split(value)` then `self._system_env.which(parts[0])`. `which` is a thin `shutil.which` wrapper, which accepts an argument containing a directory separator directly from the filesystem (so absolute paths work even off-PATH) but does NOT expand `~`.

### Environmental Triggers

None specific; deterministic. macOS/Homebrew surfaces the path-form symptom most visibly (`/opt/homebrew/...`).

### Ruled Out

- Not the Bug 63 surgical writer: `_scalar_repr` renders both `codium` and `/opt/homebrew/bin/codium` as valid plain YAML scalars (probe Q1a); the writer is faithful — the problem is the VALUE handed to it.
- Not the read path: `find_editor()` re-resolves any stored value through `shlex.split` + `which`, and `get_diff_viewer_command()` basenames for the diff-flags lookup, so basename and path behave identically downstream.
- Not the custom-command branch generally: absolute paths to non-PATH executables ARE accepted today; only the tilde form fails.

## Diagnostic Analysis

### Causal Model

The user's editor selection flows `_prompt_for_editor_selection` → `_persist_editor_choice` → `IConfigService.set_setting("editor", value)`. `discover_editors()` returns `(basename, resolved_path)` pairs; the selection handler stores element `[1]` (resolved path). On the read side `find_editor()` → `_resolve_editor_cmd` parses with `shlex.split` and resolves `parts[0]` via `which()`. Because `which` is `shutil.which` and no `expanduser` is applied, a stored `~/...` value is looked up literally and fails, while a stored absolute path succeeds (even off-PATH). Both defects are isolated to these two functions.

### Discrepancies

- Spec §4 + implementation (absolute path) vs README (`editor: "nvim"`, basename). (Resolved: three-way tension; user decided — persist basename, reconcile spec §4, leave README.)
- `~`-prefixed custom path rejected while an absolute non-PATH path is accepted: inconsistent "custom binary, not on PATH" UX. (Resolved: `which`'s directory-separator branch handles absolute/relative but not tilde; add `os.path.expanduser`.)

### Investigation History

1. Turn 26 census/read pinned the persistence site (`available[index - 1][1]`) and the read-side resolver (`shlex.split` + `which`).
2. Turn 28 probe (`spikes/debug/64-editor-value-probe.py`) observed: `_scalar_repr` plain scalar for `codium`/absolute path; round-trip writes the path form; `_resolve_editor_cmd` accepts an absolute off-PATH executable but rejects `~/…`.
3. Turn 27/29 alignment: user agreed to persist the basename; then approved the 4-item change set (basename, spec §4 reconcile, tilde expansion, README unchanged).
4. Turn 33 RED: new regression test `test_editor_value_persistence.py` failed against the old code — `set_setting("editor", "/usr/bin/nvim")` (expected `"nvim"`) and `_resolve_editor_cmd("~/bin/myeditor")` returning `None` (tilde unexpanded). Both defects reproduced.
5. Turn 34 fix: applied basename persistence (`available[index-1][1]`→`[0]`), `os.path.expanduser` in `_resolve_editor_cmd`, docstring update, and spec §4 + cli.md reconciliation. The focused run revealed TWO additional stale pinning tests (`_validate_editor_config` orchestrator tests still asserting the absolute path).
6. Turn 35 recovery: migrated both orchestrator tests to the basename form; focused run `24 passed` (GREEN).
7. Turn 36 integration: probe re-run (absolute off-PATH executable STILL resolves verbatim — `expanduser` is a no-op; command-with-flags still resolves) + full suite `1548 passed, 5 skipped`.

## Solution

### Root Cause
Two coupled portability gaps in Slice 03-01's editor handling:

1. **Non-portable persisted value.** `_prompt_for_editor_selection` (`session_cli_handlers.py`) persisted `available[index - 1][1]` — the resolved ABSOLUTE path from the `(basename, resolved_path)` pairs returned by `ConsoleToolingHelper.discover_editors()`. Spec §4 explicitly mandated this ("persist the selected editor's resolved absolute path"), but the value is machine-specific (the Homebrew prefix differs between Intel `/usr/local/bin` and Apple-Silicon `/opt/homebrew/bin`; a Windows path looks nothing like a POSIX one), so a copied `.teddy/config.yaml` does not travel between machines.

2. **Tilde paths rejected.** `ConsoleToolingHelper._resolve_editor_cmd` resolved a command string via `shlex.split(value)` + `which(parts[0])` with NO `os.path.expanduser`, so a personal binary referenced as `~/bin/myeditor` was looked up literally and rejected — even though an absolute path to the same off-PATH executable is accepted.

### Proven Fix (Implemented & Verified)
1. **Basename persistence.** `_prompt_for_editor_selection` now persists `available[index - 1][0]` (the basename). The read path re-resolves it on `PATH` (`find_editor` → `_resolve_editor_cmd` → `which`), and `get_diff_viewer_command` already basenames for the diff-flags lookup — so both forms behave identically downstream, with the basename being portable. The custom-command branch (user-typed `code --wait`) is unchanged and still persisted verbatim.
2. **Tilde expansion.** `_resolve_editor_cmd` applies `os.path.expanduser` to `parts[0]` before the `which()` call, so `~/bin/myeditor` resolves. `expanduser` is a no-op on absolute/plain paths, so off-PATH absolute paths and bare names are unaffected. This also fixes tilde paths supplied via the `VISUAL`/`EDITOR` env fallback, which flows through the same resolver.
3. **Doc reconciliation.** Spec §4 (`editor-validation-and-discovery.md`) and the CLI component doc (`docs/architecture/adapters/inbound/cli.md`) were updated from "resolved absolute path" to "basename". The README is left unchanged (per user decision — quotes are cosmetic; `nvim`, `"nvim"`, and `'nvim'` parse identically).

### Verification (RED → GREEN → integration)
- **RED (Turn 33):** new regression test `tests/suites/unit/adapters/inbound/test_editor_value_persistence.py` failed against the old code — `set_setting("editor", "/usr/bin/nvim")` instead of `"nvim"`, and `_resolve_editor_cmd("~/bin/myeditor")` returning `None`.
- **Migration (Turns 34–35):** SIX existing pinning tests in `test_session_preflight_wiring.py` asserted the retired absolute-path form and were migrated to the basename. Focused run `24 passed`.
- **MRE re-verification (Turn 36):** `spikes/debug/64-editor-value-probe.py` re-run against the fixed code — the absolute off-PATH executable STILL resolves verbatim and the command-with-flags case still resolves (proving `expanduser` introduced no collateral change).
- **Full suite (Turn 36):** `1548 passed, 5 skipped`.

### Systemic Preventative Measure
**Persist portable identifiers, not resolved paths.** A user-editable config value SHOULD store a stable, machine-independent identifier (a basename resolved on `PATH`) rather than a resolved absolute path, unless the absolute path is genuinely required. Resolved paths are environment-specific and silently break config portability.

**Categorical census:**
- The `set_setting` call-site census (Bug 63) confirmed the `editor` key is the ONLY user-config value persisted from a resolved path, so basename persistence has exactly one site.
- The tilde class ("command string resolved via `which` without `expanduser`") has a SECOND analogue: `ConsoleToolingHelper.get_diff_viewer_command` resolves the `TEDDY_DIFF_TOOL` env-var override via `shlex.split` + `which` with no `expanduser`. This is a niche, undocumented override, outside the user-approved change set, so it is logged as `[DEBT]` in `docs/project/PROJECT.md` rather than fixed here. The durable cure is to single-source the command-string resolution (one expander shared by `_resolve_editor_cmd` and the `TEDDY_DIFF_TOOL` branch).
