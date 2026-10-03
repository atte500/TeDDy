# Bug: TEDDY_DIFF_TOOL tilde path is not expanded

- **Status:** Resolved
- **Milestone:** [03-foundational-refactors.md](/docs/project/milestones/03-foundational-refactors.md)
- **Vertical Slice:** [03-01-editor-validation-and-discovery.md](/docs/project/slices/03-01-editor-validation-and-discovery.md)
- **Specs:** N/A

## Symptoms

**Expected:** When `TEDDY_DIFF_TOOL` is set to a tilde path (e.g. `~/bin/mydiff`) that points at an existing, executable binary, `ConsoleToolingHelper.get_diff_viewer_command()` should expand `~` and return the resolved absolute command (e.g. `['/Users/<user>/bin/mydiff']`).

**Actual:** The value is looked up literally — `which('~/bin/mydiff')` fails because `~` is never expanded — so the method returns `None`. The diff viewer is reported unavailable even though the tool exists and is executable. This is the same class as the editor tilde gap fixed for `_resolve_editor_cmd` in Bug 64, but it was left unfixed here and logged as `[DEBT]`.

**Minimal reproduction:** `spikes/debug/65-teddy-diff-tool-tilde-mre.py` builds a real executable in a temporary `HOME`, sets `TEDDY_DIFF_TOOL=~/bin/mydiff` process-locally, and drives the real `ConsoleToolingHelper`:

```shell
uv run python spikes/debug/65-teddy-diff-tool-tilde-mre.py
```

Expected (after fix): `PASS: tilde path resolved (bug fixed)`. Current (bug): `BUG: TEDDY_DIFF_TOOL tilde path NOT resolved (returned None)`.

## Context & Scope

### Regressing Delta
Slice 03-01 (`editor-validation-and-discovery`) introduced `ConsoleToolingHelper.get_diff_viewer_command()` with an inline `TEDDY_DIFF_TOOL` branch that hand-rolls `shlex.split(...)` + `self._system_env.which(parts[0])` with NO `os.path.expanduser`. Bug 64 (2026-10-03) added `os.path.expanduser` to the SIBLING `_resolve_editor_cmd` but did NOT touch this branch, so the tilde gap remained — exactly the defect recorded as `[DEBT]` in `docs/project/PROJECT.md` and as Milestone 5 proposed slice entry 15.

### Environmental Triggers
Any machine where `TEDDY_DIFF_TOOL` is set to a `~`-prefixed command. Deterministic; not OS-specific.

### Ruled Out
- `_resolve_editor_cmd` is already tilde-correct (Bug 64 fix); the editor resolution path is fine.
- The `diff_flags` config override branch is unrelated to this defect.

## Diagnostic Analysis

### Causal Model
`get_diff_viewer_command()` checks the `TEDDY_DIFF_TOOL` env override BEFORE the editor translation-table path. Its branch does `shlex.split(value)` then `self._system_env.which(parts[0])` with no `os.path.expanduser`. `which` is a thin `shutil.which` wrapper, which resolves an argument CONTAINING a directory separator directly on the filesystem but does NOT expand `~`. So a `~/...` value is looked up literally and fails, returning `None`. The durable cure (already noted in Bug 64): single-source the command-string resolution so `_resolve_editor_cmd` (which now expands `~`) also serves the `TEDDY_DIFF_TOOL` branch.

### Discrepancies
- A SECOND `TEDDY_DIFF_TOOL` read exists at `console_interactor.py:164` — must determine whether it shares the identical gap (partial-fix risk). (Resolved: the second site lives inside `confirm_action`'s not-found warning path; it merely prints `Warning: Custom diff tool '<name>' not found.` using `shlex.split(custom_tool)[0]` and NEVER calls `which`, so it performs no resolution and needs no expansion fix. Only `get_diff_viewer_command` resolves the command.)
- (Resolved) `TEDDY_DIFF_TOOL` is a process ENVIRONMENT VARIABLE (read via `ISystemEnvironment.get_env` → `os.getenv`), NOT a `.teddy/config.yaml` key; it is outranked by the `diff_flags` config key.

### Investigation History
1. Turn 42: Located the unfixed `TEDDY_DIFF_TOOL` branch in `get_diff_viewer_command`; built and ran the host-safe MRE (`spikes/debug/65-teddy-diff-tool-tilde-mre.py`). Observed `ACTUAL = None` vs `EXPECTED = ['<tmp>/bin/mydiff']`, with `~` correctly expanded in the process env — defect reproduced ("BUG: TEDDY_DIFF_TOOL tilde path NOT resolved").
2. Turn 44: Materialized a byte-faithful shadow replica (`spikes/debug/shadow_console_tooling.py`) via `cp` of the production module (verified: the `TEDDY_DIFF_TOOL` branch, `_resolve_editor_cmd`, and its `expanduser` line all present).
3. Turn 45–46: Confirmed the second `TEDDY_DIFF_TOOL` read (`console_interactor.py:164`) is display-only, and that the value is an env var rather than a config key.
4. Turn 47/48 (Zero-Touch Verification): Applied the single-sourcing fix to the shadow (`TEDDY_DIFF_TOOL` branch → `return self._resolve_editor_cmd(custom_tool_str)`) and re-ran the MRE with `USE_SHADOW=1`, OBSERVED `PASS: tilde path resolved (bug fixed)` — while the still-unmodified production module returns `None` (Turn 47). Fix proven without touching `src/`.
5. Turn 50 (Red Phase): Created the regression test `tests/suites/unit/adapters/outbound/test_diff_tool_tilde_expansion.py` and ran it in isolation against the unmodified production module. Observed `2 failed` — `get_diff_viewer_command()` returned `None` for `~/bin/mydiff` (and for the args variant). The test captures the defect.
6. Turn 51 (Green Phase + Integration): Ported the shadow-verified single-sourcing fix into production `src/teddy_executor/adapters/outbound/console_tooling.py`. Observed the regression test `2 passed`; the original MRE re-run against the fixed production adapter printed `PASS: tilde path resolved (bug fixed)`; the full suite closed at `1550 passed, 5 skipped`.

## Solution

### Root Cause
`ConsoleToolingHelper.get_diff_viewer_command()` resolves the `TEDDY_DIFF_TOOL` env-var override by `shlex.split(value)` then `self._system_env.which(parts[0])`. `which` is a thin `shutil.which` wrapper: it resolves an argument CONTAINING a directory separator directly on the filesystem (so absolute/relative paths work even off-PATH) but does NOT expand `~`. A value like `~/bin/mydiff` was therefore looked up literally and rejected, so the method returned `None` and the diff viewer was reported unavailable even though the expanded executable existed. This is the same class as the editor tilde gap fixed for `_resolve_editor_cmd` in Bug 64 — but that fix did not touch this branch, so the gap persisted.

### Proven Fix (Implemented & Verified)
Single-source the command-string resolution: the `TEDDY_DIFF_TOOL` branch now delegates to the canonical `_resolve_editor_cmd(custom_tool_str)`, which already applies `os.path.expanduser` (from Bug 64). The branch body was byte-for-byte that resolver MINUS the expander, so the delegation is a pure single-sourcing — no behavioural change for bare names (`meld`), commands with arguments (`meld --auto-compare`), or non-existent tools (still returns `None`). `shlex` remains imported (still used by `_resolve_editor_cmd`).

### Verification (shadow → RED → GREEN → integration)
- **Shadow (Turn 47/48):** applied the fix to the byte-faithful replica and re-ran the MRE with `USE_SHADOW=1` → `PASS`; production still returned `None`.
- **RED (Turn 50):** new permanent regression test `tests/suites/unit/adapters/outbound/test_diff_tool_tilde_expansion.py` → `2 failed` on unmodified `src/`.
- **GREEN (Turn 51):** ported the fix to production → regression test `2 passed`; MRE re-run against the real adapter → `PASS: tilde path resolved (bug fixed)`.
- **Full suite (Turn 51):** `1550 passed, 5 skipped`.

### Systemic Preventative Measure
**Single-source command-string resolution.** When the same "parse a command string and resolve its executable" concern appears in more than one branch (here the editor path and the `TEDDY_DIFF_TOOL` override), it MUST funnel through ONE resolver so a fix to one branch automatically covers all of them. The Bug 64 fix patched `_resolve_editor_cmd` in isolation; had this branch already delegated to it, the `TEDDY_DIFF_TOOL` tilde gap would never have existed. The `[DEBT]` entry in `docs/project/PROJECT.md` and the Milestone 5 proposed slice entry 15 are REMOVED as resolved by this change.
