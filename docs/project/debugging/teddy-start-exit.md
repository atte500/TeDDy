# Bug: `teddy start` exits after first turn

- **Status:** Resolved

## 1. Failure Context
When a user runs `teddy start`, the system asks for the first prompt, plans, executes the plan, and then immediately exits to the shell instead of continuing the conversational loop.

## 2. Steps to Reproduce
1. Run `teddy start`
2. Provide a prompt (e.g., "this is a test")
3. Wait for planning and execution.
4. CLI exits.

## 3. Expected vs. Actual Behavior
- **Expected:** The CLI stays open and prompts the user for the next instruction (continuous loop).
- **Actual:** The CLI exits after generating the first execution report.

## 4. Relevant Code
`src/teddy_executor/adapters/inbound/session_cli_handlers.py` (specifically `handle_new_session` vs `handle_resume_session`).

## 5. Investigation Log
- Found that `handle_resume_session` was updated in Slice 10-08 to include a `while True:` loop around `orchestrator.resume(...)`.
- Found that `handle_new_session` (the handler for `teddy start`) still uses a single, un-looped call to `orchestrator.resume(...)`.

## 6. Root Cause Analysis
The continuous loop feature added in Slice 10-08 was implemented for the `resume` command but overlooked for the `start` command in `session_cli_handlers.py`.

Additionally, a naive `while True:` loop fails because `teddy start` performs an auto-rename of the session directory based on the first plan's title (H1). This makes the initial `actual_name` stale for the second iteration of the loop.

## 7. Implementation Notes
The fix involves:
1. Wrapping the `orchestrator.resume` call in `handle_new_session` within a `while True:` loop.
2. Dynamically re-resolving the `current_session_name` at the end of every loop iteration using `session_manager.get_latest_session_name()`. Since the session being worked on was the most recently active, this reliably handles renames.
3. Added a regression test `test_start_enters_continuous_loop` in `tests/suites/acceptance/test_session_resume_robustness.py`.
