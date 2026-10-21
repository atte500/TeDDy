# Bug: Editor-Open State Persists Across Turns
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc defect)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Expected: each new turn renders the `Response (type 'e' for editor) › ` prompt, and the editor temp file is removed when its content is not harvested.

Actual: after the editor is opened once, the next turn renders `Editor opened. Terminal reply or [Enter] to confirm editor › ` immediately. The temp file survives when the user replies with terminal text instead of pressing [Enter].

Minimal reproduction:
1. Start or resume an interactive session (`teddy resume`).
2. At `Response (type 'e' for editor) › `, type `e` and press Enter.
3. At `Editor opened. Terminal reply or [Enter] to confirm editor › `, reply with terminal text instead of pressing Enter.
4. Complete the turn and observe the prompt on the next turn.

## Context & Scope
### Regressing Delta
`4889def1` (feat(editor-subsystem-overhaul): implement Logic (Console) deliverable) replaced the blocking `_open_editor_blocking` helper with the persistent `_active_editor_path` model. The retired helper deleted its temp file in a `finally` block. The replacement returns terminal input through `if user_input: return user_input` without clearing `_active_editor_path` or deleting the draft.

File: `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py`, lines 50 (state field), 112-122 (prompt selection), 218-220 (CLI cleanup), 248-263 (empty-input harvest).

### Environmental Triggers
Interactive console session with a GUI editor (`codium`) on macOS 25.5.0.

### Ruled Out
- Interactor registration scope is not the cause. `IUserInteractor` is registered as `punq.Scope.transient`, yet `_orchestrate_session_loop` resolves `IRunPlanUseCase` once before its `while True` loop. That single resolution pins one interactor and one ask loop for the whole session.
- Temp-file deletion is not the cause. `SystemEnvironmentAdapter.delete_file` unlinks only when the path exists.
- The empty-input harvest path is not the leak site. `_handle_empty_input` deletes the draft and clears the field.
- The CLI editor path is not the leak site. `_launch_editor_background` deletes the draft and clears the field before returning harvested content.

## Diagnostic Analysis
### Causal Model
1. The session boundary resolves `IRunPlanUseCase` once, so a single `ConsoleInteractorAdapter` and its single `ConsoleAskLoop` serve every turn.
2. Typing `e` sends a GUI editor down the fire-and-forget branch. That branch stores the draft path in `_active_editor_path` and returns an empty string.
3. The loop re-renders the prompt and the populated field selects the `Editor opened. Terminal reply or [Enter] to confirm editor › ` text.
4. A non-empty terminal reply reaches `if user_input: return user_input`. That return skips the draft deletion and the field reset, so both survive the turn.
5. The next turn calls `run()` on the same instance. The stale field selects the `Editor opened` prompt immediately, and the draft file stays on disk.

### Discrepancies
- [x] The next turn shows `Editor opened` instead of the fresh `Response (type 'e' for editor)` prompt. (Resolved: the terminal-reply return path now calls `_discard_pending_draft`, so the stale `_active_editor_path` never survives the turn.)
- [x] The editor temp file persists when the terminal reply path bypasses harvesting. (Resolved: the same discard helper deletes the draft file, and the failed-harvest branch now deletes it too.)

### Investigation History
1. Located the prompt strings and the editor lifecycle in `console_interactor_ask_loop.py` via `git grep`. The editor state lives in `_active_editor_path`. The empty-input harvest path clears that field and deletes the file; the non-empty reply path reads `if user_input: return user_input` without cleanup.
2. Traced the holder chain with `git grep`, `sed`, and the container reads. `_orchestrate_session_loop` resolves `IRunPlanUseCase` once before `while True`, so one interactor and one ask loop serve every turn.
3. Ran `git log -S "_active_editor_path"` and `git show 4889def1`. The overhaul replaced the blocking editor helper, which deleted its temp file in `finally`, with the persistent draft model and added no cleanup on the terminal-reply branch.
4. Built `spikes/debug/editor-open-state-persistence/01-editor-open-state-mre.py`. It drives one ask-loop instance through two turns with a simulated GUI editor spawn. The first run failed on the prompt_toolkit `history` keyword; accepting `**kwargs` fixed the probe. Against production it reports the stale turn-2 prompt and the leaked draft file.
5. Confirmed `SystemEnvironmentAdapter.delete_file` tolerates a missing path, so an unconditional discard is safe.
6. Built [replica_console_interactor_ask_loop.py](/spikes/debug/editor-open-state-persistence/replica_console_interactor_ask_loop.py) with the discard helper and ran [01-editor-open-state-mre.py](/spikes/debug/editor-open-state-persistence/01-editor-open-state-mre.py) against both targets. Production reproduced both symptoms; the replica removed the draft and restored the fresh prompt. Applied the proven change to `src/`, added two regression tests, and ran the full suite green.

## Solution
### Root Cause
`ConsoleAskLoop.run()` returned terminal input through `if user_input: return user_input` without clearing `_active_editor_path` or deleting the draft file. The session boundary resolves `IRunPlanUseCase` once, so one ask-loop instance serves every turn. The first `e` spawns the GUI editor and stores the draft path. A terminal reply then returns with the field still set, so the next turn selects the "Editor opened" prompt and the temp file stays on disk. The regressing commit `4889def1` introduced the persistent draft model and dropped the `finally` cleanup that the retired blocking helper carried. The fix was applied directly to production after the sandbox replica proved it: `run()` now calls `_discard_pending_draft()` on the terminal-reply path, and the failed-harvest branch deletes the draft and logs the failure. Two regression tests cover the reported sequence. The full suite passes (1951 passed, 5 skipped), and the preserved MRE reports no stale prompt and no leaked draft against production.

### Affected Components
- `ConsoleAskLoop` (`src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py`): Added `_discard_pending_draft`, called it on the terminal-reply return path, and hardened the failed-harvest branch.
- `ConsoleInteractorAdapter` (`src/teddy_executor/adapters/outbound/console_interactor.py`): No code change. It creates one ask loop and delegates `ask_question` to `run()`.
- `SessionOrchestrator` and the session loop (`session_cli_handlers.py`): No code change. They pin one interactor across turns, which the fix relies on.
- `SystemEnvironmentAdapter.delete_file`: No change. The adapter already tolerates a missing path.
- `tests/suites/unit/adapters/outbound/test_console_ask_loop_wiring.py`: Added two regression tests for the abandoned-draft cleanup.
- `docs/architecture/adapters/outbound/console_interactor.md`: Recorded the draft cleanup in the `ask_question` postcondition.
