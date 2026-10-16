# Slice: Session Startup Banner Consistency & Startup Consolidation
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** [interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `session-banner`

## Business Goal
Make `teddy start` and `teddy resume` print startup banners with identical spacing so the session path always sits directly beneath the Agent/Model identity block. Consolidate the duplicated startup preamble and error handler so the two entry points cannot drift apart.

## Scenarios
> As a TeDDy user, I want a consistent startup banner whether I start or resume a session.

```gherkin
Given a configured workspace
When the user runs `teddy start`
Then the Agent/Model identity block is followed immediately by the session path line with no blank line between them
```

```gherkin
Given an existing session
When the user runs `teddy resume`
Then the Agent/Model identity block is followed immediately by the session path line with no blank line between them
```

## Edge Cases
- **No agent**: When `_echo_config_success` runs without an agent, the identity block holds only the Model line, and the session path line still follows immediately.
- **Notification channels**: Enabling or disabling the drift and update checks does not alter the banner spacing.
- **Error path**: A `ConfigurationError` still prints the error and the config hint, and the shared handler preserves that behavior.

## Key Unknowns
- [x] [Functional] Desired spacing: resolved. No blank line separates `Model:` from the session path line, matching the current `teddy start` output.
- [x] [Functional] Session-line wording: resolved. The text stays command-specific ("Session created at:" for start, "Resuming session:" for resume) because each names a distinct event. Only the spacing unifies.
- [x] [Technical] Root cause: resolved. `handle_resume_session` echoes `f"\nResuming session: ..."` with a leading newline, while `handle_new_session` echoes `f"Session created at: ..."` with none.
- [x] [Technical] Blast radius: resolved. No test asserts either banner string, so the fix extends coverage rather than breaking it.

## Impact
The change is module-local to `session_cli_handlers.py`. No port, DTO, or shared contract changes, so no Parallel Change partitioning is required.

1. `[MIGRATE]` `session_cli_handlers.handle_resume_session` — drop the leading newline from the session-path echo.
2. `[REFACTOR]` `session_cli_handlers` — extract the shared startup preamble and error handler.

## Deliverables
- [x] **Harness** - Add regression tests pinning the banner spacing for both `handle_new_session` and `handle_resume_session`, since no test currently asserts either banner string.
- [x] **Logic** - Remove the leading `\n` from `handle_resume_session`'s `Resuming session:` echo so both entry points share identical banner spacing.
- [x] **Refactor** - Extract the duplicated session-startup preamble (background update thread, update-notification capture, health checks, `Checking configurations...` preflight, disable-footer) and the identical `ConfigurationError` and generic error handler into shared module-level helpers. Preserve the intended differences: `handle_new_session` passes `agent` to the preflight and resolves the message and session, while `handle_resume_session` resolves the session name and syncs meta.

## Implementation Notes
The banner-emission helper `_echo_config_success` is already shared by both entry points, so only the surrounding startup preamble and the error handler need consolidation. Milestone 6 does not schedule this duplication, so it is slice-scoped refactoring rather than cross-cutting debt. The user's report showed two command outputs divided by a separator, not one command emitting two banners.

**Harness (banner regression pin).** Added `tests/suites/unit/adapters/inbound/test_session_startup_banner.py`, which drives both handlers through the `env` fixture and captures stdout/stderr via `capsys`. The tests pin the CURRENT spacing: `start` emits `Session created at: ...` with no leading blank line, and `resume` emits `\nResuming session: ...` with a leading blank line. The pin is green against current behavior; the Logic deliverable flips the resume expectation when it drops the leading newline. The identity block reads `Agent: Pathfinder` because `_echo_config_success` canonicalizes the agent name.

**Logic (unified spacing).** Removed the leading `\n` from `handle_resume_session`'s `Resuming session:` echo so the session path line sits directly beneath the identity block, matching `start`. The Red step flipped the resume assertion in `test_session_startup_banner.py` to `"Resuming session: .teddy/sessions/my-session\n"` and observed the expected `AssertionError` against the actual leading newline; the Green step removed the newline and both banner tests passed.

**Refactor (shared startup helpers).** Extracted three module-level helpers so the two entry points cannot drift. `_start_background_update_check(container)` spawns the daemon version thread and returns the update-check keys from `_display_update_notification`. `_run_startup_preamble(container, fired, agent, setup_editor, setup_api_key)` runs the fixed-order preamble: `_run_health_checks()`, the `Checking configurations...` line, `_run_cli_preflight_check(...)` whose returned keys extend `fired`, then `_display_checks_footer(fired)`. `_handle_startup_error(container, error)` prints the error and exits with code 1, adding the config-path hint for `ConfigurationError`. Both identical `except` blocks collapsed to one `_handle_startup_error(container, e)` call. Added `tests/suites/unit/adapters/inbound/test_session_startup_helpers.py`, which pins the routing (both handlers call both helpers, `start` forwards `agent` while `resume` passes none) and the error-handler contract (config hint for `ConfigurationError`, plain line otherwise). The Red step observed four `AttributeError` failures for the not-yet-existent helpers; the Green step extracted them and the inbound adapter suite passed (`272 passed`).

## Verification
- [ ] **CLI**: Run `teddy start -m hi` and verify the session path line sits directly beneath the `Model:` line with no blank line between them.
- [ ] **CLI**: Run `teddy resume` and verify the same spacing.
- [ ] **CLI**: Confirm both commands emit an identical banner layout.
- [ ] `make test` (full suite) is GREEN.
