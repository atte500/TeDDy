# Slice: Silent-on-Resume Workspace Bootstrap
- **Status:** In Progress
- **Milestone:** Ad-hoc
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `silent-resume`

## Goal
On `teddy resume`, run the workspace `git init` and pre-commit shim repairs without printing any banner line, while `teddy start` keeps its workspace banner byte-for-byte. This quiets the resume banner without dropping the mid-session repair path.

## Context
- `session_cli_handlers._run_startup_preamble`: shared by `start` and `resume`. It runs `_run_health_checks(config_service)`, runs `_pull_workspace_on_start` only when `pull_workspace` is set, echoes one separator blank, prints `Checking configurations...`, then the update notice and the preflight check.
- `session_cli_handlers._run_health_checks(config_service)`: gates `_ensure_commit_hooks()` on `workspace.pre-commit` and `_check_git_initialized()` on `workspace.init`; each helper prints exactly one green or one yellow line to `stderr`.
- `session_cli_handlers._ensure_commit_hooks()`: idempotent check-and-repair of the pre-commit and post-commit shims. It prints green on success and yellow on missing config, missing CLI, CLI lookup failure, or a failed install.
- `session_cli_handlers._check_git_initialized()`: idempotent `.git` check-and-repair. It prints green on detected or freshly initialized and yellow on missing CLI, lookup failure, or a failed init.
- `session_cli_handlers._echo_config_success` (reached from `start` directly and from `resume` through `_sync_and_display_session_meta`): emits the leading `\n` before the `Agent:`/`Model:` block. That newline is the empty line after `Checking configurations...`.
- `tests/suites/unit/adapters/inbound/test_session_startup_banner.py`: pins resume stderr as `"\nChecking configurations...\n\nModel: gpt-4o\n"` with `_run_health_checks` stubbed, and start stderr as `"\nChecking configurations...\n\nAgent: Pathfinder\nModel: gpt-4o\n"`.
- `handle_new_session` already passes `pull_workspace=True`; `handle_resume_session` leaves it off and passes no agent.

## Scenarios

> As a user resuming a healthy session, I want a quiet workspace banner so resume output is not cluttered with confirmations I already know.

```gherkin
Given a workspace with .git present, the pre-commit CLI on PATH, and hook shims current
And every workspace toggle is enabled
When teddy resume runs
Then stderr shows no "✓ pre-commit hooks installed" line and no "✓ Git repository detected" line
And stderr shows "Checking configurations..." followed by a blank line and then the Model line
And stderr does not begin with a blank line
```

> As a user starting a new session, I want the workspace banner to stay the same.

```gherkin
Given the same healthy workspace
When teddy start runs
Then the banner still shows "✓ pre-commit hooks installed" and "✓ Git repository detected"
And the "✓ Workspace up-to-date with remote" line still appears
```

> As a user resuming on a workspace with a missing pre-commit CLI, I want the repair attempted silently.

```gherkin
Given a workspace where the pre-commit CLI is not on PATH
When teddy resume runs
Then no "⚠ pre-commit CLI not found" warning appears
And running teddy start in the same condition still prints that warning
```

## Edge Cases
- **Repair still runs on resume**: If a workspace needs `git init` or a shim reinstall, then resume still performs it, because only the output is silenced, not the repair.
- **Full silence on resume**: If a helper fails (missing CLI, failed install, failed init), then resume prints nothing, because full silence on resume is an explicit product decision; `start` still surfaces every warning.
- **Blank after `Checking configurations...`**: The empty line before `Agent:`/`Model:` stays on both entry points, because `_echo_config_success` owns it and is untouched.
- **No orphan leading blank on resume**: If the resumed workspace block emits nothing, then the preamble separator blank is suppressed, so resume output does not open with a blank line.
- **Start output unchanged**: If the workspace toggles are enabled, then `teddy start` output stays byte-for-byte identical, including the separator blank and both green lines.
- **Both toggles disabled**: If `workspace.init` and `workspace.pre-commit` are both `false`, then no workspace line prints on either entry point (already true today), and resume still avoids a leading blank.

## Key Unknowns
No open unknowns. The design is settled: full silence on resume including warnings, the post-`Checking` blank preserved, the repair still runs on resume, and no orphan leading blank on resume. The pattern is established and no prototype is needed.

## Impact
1. `[EXPAND]` `_run_startup_preamble` — add `verbose_workspace: bool = False` and forward it to `_run_health_checks`.
2. `[EXPAND]` `_run_health_checks`, `_ensure_commit_hooks`, `_check_git_initialized` — add a `verbose: bool = True` parameter that gates every `typer.secho` while leaving the repair side effects unconditional.
3. `[MIGRATE]` `handle_new_session` — pass `verbose_workspace=True`; `handle_resume_session` keeps the default `False`.
4. `[MIGRATE]` `_run_startup_preamble` separator — emit the separator blank only when a workspace line is printed above it, so resume does not open with an orphan blank while `start` stays identical.
5. `[MIGRATE]` `config.yaml` comments and the `cli.md` startup-preamble contract — document that the workspace steps run on both entry points but report only on `start`.

## Deliverables
- [x] **Core** — Add `verbose: bool = True` to `_run_health_checks`, `_ensure_commit_hooks`, and `_check_git_initialized`; gate every `typer.secho` on `verbose`; keep all repair side effects unconditional; forward `verbose` from `_run_health_checks` to both helpers. Write the silencing tests first (Red), including coverage that a silenced helper still performs its repair, and update the two helper stubs that assert the call signature so they accept the forwarded keyword.
- [x] **Wiring** — Add `verbose_workspace: bool = False` to `_run_startup_preamble`, forward it as `_run_health_checks(config_service, verbose=verbose_workspace)`, and pass `verbose_workspace=True` from `handle_new_session` while `handle_resume_session` keeps the default `False`. Pin the forwarded flag in the start-vs-resume recorder pair. The separator blank stays unconditional so this commit is green: resume silences the workspace lines but still emits the blank the current banner assertion expects.
- [x] **Wiring** — Gate the preamble separator blank on `verbose_workspace` so resume does not open with a leading blank while `start` stays byte-identical, and update the resume banner assertion in `test_session_startup_banner.py` to drop the leading newline in the same commit (the start assertion stays byte-identical).
- [ ] **Cleanup** — Update the `workspace.init` and `workspace.pre-commit` comments in `config.yaml`, the `start_only_workspace_pull` invariant, and the startup-preamble section of `docs/architecture/adapters/inbound/cli.md`.

## Implementation Notes
- **Core (verbose plumbing):** `_ensure_commit_hooks`, `_check_git_initialized`, and `_run_health_checks` now take `verbose: bool = True`. Every banner line routes through one `_workspace_notice(verbose, message, color)` gate; the `git init` and `pre-commit install` repairs run unconditionally, so a silent call still heals the workspace. `_run_health_checks` forwards `verbose` to both helpers. The default `True` keeps every existing zero-arg caller byte-identical, so no shared-seam break.
- **Red/Green evidence:** New `tests/suites/unit/adapters/inbound/test_workspace_verbose_silencing.py` failed Red with `TypeError: unexpected keyword argument 'verbose'` (4 failed, 1 passed), then passed Green (5 passed). The two forwarding stubs (`test_run_health_checks_calls_both`, `test_workspace_config_toggles.py`) were loosened to `**kwargs` in the same cycle so the contract change stayed atomic. Full suite: 2127 passed, 5 skipped.
- **Wiring #2 (verbose_workspace forwarding):** `_run_startup_preamble` now takes `verbose_workspace: bool = False` and forwards it as `_run_health_checks(config_service, verbose=verbose_workspace)`; `handle_new_session` passes `verbose_workspace=True` while `handle_resume_session` keeps the default `False`. The separator blank stays unconditional in this commit on purpose, so the current resume banner assertion (`"\nChecking configurations...\n\nModel: gpt-4o\n"`) still passes — the orphan-blank removal is Wiring #3. Red: the recorder pair failed on `verbose_workspace is True` being `None` plus `TypeError: _run_startup_preamble() got an unexpected keyword argument 'verbose_workspace'` (2 failed, 6 passed). Green: 8 passed. Full suite: 2128 passed, 5 skipped.
- **Wiring #3 (separator gating):** `_run_startup_preamble` now guards the separator blank with `if verbose_workspace:`, so `start` (`verbose_workspace=True`) keeps its blank byte-for-byte while `resume` (default `False`) never opens with an orphan leading blank. The preamble docstring now states the gating. The resume banner assertion in `test_session_startup_banner.py` was flipped to `"Checking configurations...\n\nModel: gpt-4o\n"` (no leading newline); the start assertion is unchanged. Red: the resume test failed on the missing leading blank (1 failed, 3 passed). Green: 4 passed. Full suite: 2128 passed, 5 skipped.

## Verification
1. **Silent resume:**
   Run `teddy resume` in a healthy workspace.
   Verify stderr shows no `✓ pre-commit hooks installed`, no `✓ Git repository detected`, and no warning, and that `Checking configurations...` is followed by a blank line and the `Model:` line with no blank line above `Checking configurations...`.
2. **Unchanged start:**
   Run `teddy start` in the same workspace.
   Verify the two workspace green lines and the pull line are byte-identical to the previous release.
3. **Silent broken resume:**
   Remove `pre-commit` from `PATH` and run `teddy resume`.
   Verify no `⚠ pre-commit CLI not found` warning appears, then run `teddy start` and verify the warning still appears.
