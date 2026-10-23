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
- `session_cli_handlers._pull_workspace_on_start`: reports one generic checkmark skip notice for every unsafe state, without naming the reason.

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
- **Dirty worktree**: If tracked changes exist, then it prints the skipped warning with no extra trailing blank line.
- **Skip notice**: If the HEAD is detached, the upstream is missing, or a Git operation is in progress, then it prints one generic checkmark skip notice without the reason, because the user needs a pull outcome but not the diagnostic detail.
- **Disabled pull or non-repository**: If the pull check does not run, then no pull line appears, because no remote status exists.
- **Disabled health checks**: If every health check is disabled and the block is empty, then one leading blank line precedes `Checking configurations...`. This is accepted for simplicity.
- **Drift and footer**: If notices exist, then they abut `Checking configurations...`, and the identity block keeps its single leading blank line.
- **Pull warning**: If the pull fails, times out, or git is unavailable, then one yellow warning appears in the checkmark block with no extra trailing blank line.

## Key Unknowns
No open unknowns. The skip-notice behavior is a recorded product decision, not an unresolved ambiguity.

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

## Implementation Notes
The update notification is emitted before the checkmark block. It now prints to stderr, so its trailing newline no longer splits the banner across two streams.

Pathfinder executes this slice directly, because the user approved a self-contained change over one production module plus its asserting tests. The drift notices, the disable footer, and the update notice now print to stderr, so a redirected run keeps the banner order.

A follow-up direct change replaced the silent unsafe pull skips with checkmark skip notices. The banner therefore reports a pull outcome on every run without claiming the workspace is up to date.

A final refinement collapsed the three skip reasons into one generic `✓ Workspace pull skipped` notice, because the reason adds noise without changing what the user does. The dirty-worktree and timeout warnings also dropped their continuation clauses for the same reason.

The acceptance pull test asserts the fast-forward line as a substring, so it needed no change. The up-to-date line is pinned by the unit pull-outcome test instead. The separator blank line is unconditional, so a run with every check disabled opens with one empty line. This trade-off keeps the preamble assembly simple.

## Verification
1. **Up-to-date start:**
   Run `teddy start` in a clean repository that is up to date with its remote.
   Verify the block ends with `✓ Workspace up-to-date with remote`, then one blank line, then `Checking configurations...`.
2. **Drift notices:**
   Run `teddy start` when a prompt differs from the bundled default.
   Verify each notice sits directly under `Checking configurations...` and one blank line precedes `Agent:`.
