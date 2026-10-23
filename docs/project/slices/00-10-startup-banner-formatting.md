# Slice: Startup Banner Formatting
- **Status:** Completed
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** None
- **Scope Slug:** `startup-banner`

## Goal
Group the startup checkmark lines, always report the workspace pull outcome, and normalize banner spacing so notices sit directly under `Checking configurations...`.

## Context
Key findings from static code reading of `src/teddy_executor/adapters/inbound/session_cli_handlers.py`.
- `session_cli_handlers._run_startup_preamble`: prints health checks, the optional pull line, `Checking configurations...`, the preflight drift block, and the shared disable footer.
- `session_cli_handlers._warn_pull`: prints one yellow warning with no trailing blank line.
- `session_cli_handlers._report_fast_forward`: prints the fast-forward line with no trailing blank line, and reports the up-to-date notice when no commit moves.
- `session_cli_handlers._display_drift_notification`: prints the drift block directly under `Checking configurations...`.
- `session_cli_handlers._echo_config_success`: prepends a blank line before the identity block.
- `session_cli_handlers._pull_workspace_on_start`: warns once for every skip and every failure, naming the cause, so a skipped pull carries no checkmark.

## Scenarios
Primary user journeys and happy paths.

> As a developer starting a session, I want a compact startup banner so I can scan checkmarks and notices quickly.

```gherkin
Given the workspace is a Git repository that is up to date with its remote
And workspace.pull is enabled
When I run `teddy start`
Then the checkmark block ends with "✓ Workspace up-to-date with remote"
And exactly one blank line follows the block
And "Checking configurations..." follows the blank line
```

```gherkin
Given the workspace is behind its remote
When I run `teddy start`
Then the checkmark block ends with "✓ Workspace fast-forwarded (N commits)"
And exactly one blank line follows the block
```

```gherkin
Given a prompt or template has drifted from the bundled defaults
When I run `teddy start`
Then each notice sits directly under "Checking configurations..."
And exactly one blank line separates the last notice from the Agent block
```

```gherkin
Given I resume an existing session
When I run `teddy resume`
Then the same spacing rules apply
And no workspace pull line appears
```

## Edge Cases
Boundary conditions and validation cases.
- **No-op pull**: If a successful pull moves no commit, then it prints `✓ Workspace up-to-date with remote`, because the user needs positive confirmation.
- **Fast-forward**: If the pull moves commits, then it prints `✓ Workspace fast-forwarded (N commits)`.
- **Dirty worktree**: If tracked changes exist, then it prints `⚠ Workspace pull skipped: N uncommitted file(s).`, because the count shows how much work stands between the user and a pull.
- **Detached HEAD**: If the HEAD is detached, then it prints `⚠ Workspace pull skipped: detached HEAD.`, because a skipped pull is never a verified pass.
- **Missing upstream**: If the branch has no upstream, then it prints `⚠ Workspace pull skipped: no upstream branch.`.
- **In-progress operation**: If a merge, rebase, or cherry-pick is running, then it prints `⚠ Workspace pull skipped: Git operation in progress.`, because that is a risky moment to start a session.
- **Not a repository**: If the pull is enabled but the workspace has no `.git`, then it prints `⚠ Workspace pull skipped: not a Git repository.`, because the user asked for a pull outcome on every run.
- **Disabled pull**: If `workspace.pull` is disabled, then no pull line appears, because the user opted out.
- **Disabled workspace gate**: If `workspace.init` or `workspace.pre-commit` is disabled, then its step is skipped and no warning names the opt-out, because the setting is the user's own choice.
- **Failed pull**: If the pull returns non-zero, then it prints `⚠ Workspace pull failed.`, so a real failure never looks like a deliberate skip.
- **Timeout or missing git**: If the pull times out or git is unavailable, then it prints `⚠ Workspace pull timed out after 15s.` or `⚠ Workspace pull failed: git is unavailable.`.
- **Disabled health checks**: If every health check is disabled and the block is empty, then one leading blank line precedes `Checking configurations...`. This is accepted for simplicity.
- **Drift and footer**: If notices exist, then they abut `Checking configurations...`, and the identity block keeps its single leading blank line.

## Key Unknowns
No open unknowns. The all-yellow pull outcome policy is a recorded product decision, not an unresolved ambiguity.

## Impact
Affected components and non-breaking migration order.
1. `[MIGRATE]` `session_cli_handlers._run_startup_preamble` — own the single separator blank line before `Checking configurations...`.
2. `[MIGRATE]` `session_cli_handlers._warn_pull` and `_report_fast_forward` — stop appending trailing blanks and report the no-op status.
3. `[MIGRATE]` `session_cli_handlers._display_drift_notification` — stop prepending a blank line.
4. `[MIGRATE]` Existing banner and pull tests — assert the new spacing and the up-to-date line.

## Deliverables
- [x] **Wiring** - Emit one blank line before `Checking configurations...` in `_run_startup_preamble`.
- [x] **Logic** - Report `✓ Workspace up-to-date with remote` on a no-op pull and remove the trailing blank from pull lines.
- [x] **Logic** - Remove the leading blank from `_display_drift_notification`.
- [x] **Migration** - Update `tests/suites/unit/adapters/inbound/test_session_startup_banner.py` and `tests/suites/unit/adapters/inbound/test_workspace_config_toggles.py` so they pin the new spacing and the up-to-date line.
- [x] **Logic** - Report a checkmark skip notice for a detached HEAD, a missing upstream, and an in-progress Git operation.
- [x] **Migration** - Move the drift notices, the disable footer, and the update notice to stderr.
- [x] **Logic** - Collapse the skip reasons into one generic checkmark notice and drop the continuation clauses from the pull warnings.
- [x] **Logic** - Warn with the cause for every pull skip, count the blocking files, and split the failed pull from the deliberate skip.
- [x] **Cleanup** - Retire the generic skip notice, the green pull helper, and the disabled-gate warnings.

## Implementation Notes
The update notification is emitted before the checkmark block. It now prints to stderr, so its trailing newline no longer splits the banner across two streams.

Pathfinder executes this slice directly, because the user approved a self-contained change over one production module plus its asserting tests. The drift notices, the disable footer, and the update notice now print to stderr, so a redirected run keeps the banner order.

A follow-up direct change replaced the silent unsafe pull skips with checkmark skip notices. The banner therefore reports a pull outcome on every run without claiming the workspace is up to date.

A final refinement collapsed the three skip reasons into one generic `✓ Workspace pull skipped` notice, because the reason adds noise without changing what the user does. The dirty-worktree and timeout warnings also dropped their continuation clauses for the same reason.

A later refinement reversed that collapse. A checkmark asserts a verified pass, and a skipped pull was never attempted, so every skip is now a warning that names its cause. The dirty-worktree warning reports the blocking file count, the failed pull gets its own message, the timeout names its configured budget, and the disabled-gate reminders were removed because the opt-out is the user's own choice.

The acceptance pull test asserts the fast-forward line as a substring, so it needed no change. The up-to-date line is pinned by the unit pull-outcome test instead. The separator blank line is unconditional, so a run with every check disabled opens with one empty line. This trade-off keeps the preamble assembly simple.

## Verification
1. **Up-to-date start:**
   Run `teddy start` in a clean repository that is up to date with its remote.
   Verify the block ends with `✓ Workspace up-to-date with remote`, then one blank line, then `Checking configurations...`.
2. **Drift notices:**
   Run `teddy start` when a prompt differs from the bundled default.
   Verify each notice sits directly under `Checking configurations...` and one blank line precedes `Agent:`.
3. **Dirty worktree:**
   Leave two tracked files modified in a repository that has an upstream.
   Run `teddy start`.
   Verify the block ends with `⚠ Workspace pull skipped: 2 uncommitted files.`
