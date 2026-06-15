# Bug: Console Output Visibility Bugs (4 issues)
- **Status:** Resolved
- **Milestone:** [02-stability-and-polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [00-01-console-and-message-visibility](/docs/project/slices/00-01-console-and-message-visibility.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms

### Bug #1: Initial Request shown on every turn instead of only once
- **Expected:** The "Initial Request:" label and content should only appear at the very beginning of a session (turn 01).
- **Actual:** The initial request is displayed on every subsequent turn as well.
- **Context:** A fix was applied in Turns 43-44 via a `turn_number == "01"` guard in `session_lifecycle_manager.py`'s `_handle_planning_and_execution()`. However, a duplicate call path in `session_orchestrator.py`'s `execute()` method does not have this guard.

### Bug #2: Missing empty line between "Session created" and "Initial Request"
- **Expected:** There should be a blank line between "Session created at: ..." and "Initial Request:".
- **Actual:** These two lines appear directly adjacent without proper spacing.
- **Context:** The `_print_initial_request` helper previously emitted a trailing blank line via `typer.secho("")` which was removed in Turns 43-44 as part of the duplicate fix. The spacing fix may be incomplete.

### Bug #3: User Message not showing after reply
- **Expected:** After the user provides a reply during execution (via the 'm' key in TUI), "User Message:" should appear in the console output.
- **Actual:** The user message is not displayed.
- **Context:** A fix in Turns 43-44 changed the wiring to read from `plan.metadata["user_request"]` which is populated by `_dispatch_single_action`. However, the production code in `execute()` still passes the `message` parameter (which is None for replies) instead of the metadata value.

### Bug #4: PromptManager: Failed to resolve system prompt (searched None and None)
- **Expected:** No error/warning should be printed about failed system prompt resolution.
- **Actual:** The message `PromptManager: Failed to resolve system prompt for agent 'Pathfinder' (searched None and None)` appears in the output.
- **Context:** This occurs because the `fetch_system_prompt` method stores `None` in `session_root_prompt` and `teddy_prompt_path` when it cannot find a prompt file, and the `%s` formatting in the logging call converts these to the string "None".

## Context & Scope

### Regressing Delta
This is not a single regression but a set of related bugs in the console visibility feature implemented in slice `00-01-console-and-message-visibility`. The affected components are:
1. `src/teddy_executor/core/services/session_orchestrator.py` - `_print_initial_request`, `_print_header_bar`, `_print_user_message` helpers and their call sites in `execute()`.
2. `src/teddy_executor/core/services/session_lifecycle_manager.py` - The `_print_initial_request` call in `_handle_planning_and_execution()`.
3. `src/teddy_executor/core/services/prompt_manager.py` - `fetch_system_prompt()` method with the logging issue.

### Environmental Triggers
- Requires session mode (is_session=True).
- For bugs #1-#3: Requires a running session with user-provided messages.
- For bug #4: Requires that the session root or `.teddy/prompts/` does NOT contain the agent prompt file.

### Ruled Out
- The `_print_header_bar` helper is not implicated in any reported bug.
- The Tee installation logic in both `session_orchestrator.py` and `session_lifecycle_manager.py` is not directly related.
- The `_handle_aborted_session` method is not related.

## Diagnostic Analysis

### Causal Model

**Bug #1 (CONFIRMED):** The `execute()` method in `session_orchestrator.py` calls `_print_initial_request()` at lines 185-188. This call path is reached on EVERY turn via the `elif is_session and plan_path:` branch, which reads `initial_request.md` from disk. There is NO turn_number guard, unlike the lifecycle manager's `_handle_planning_and_execution()` which has `if turn_number == "01":`. The probe confirmed that calling `_print_initial_request(None, True, plan_path=...)` for turn "02" with `initial_request.md` present produces output ("Initial Request:" label and content).

**Bug #2 (CONFIRMED):** The `_print_initial_request` helper in `session_orchestrator.py` does NOT emit a trailing blank line. The probe confirmed exactly 2 calls to `typer.secho`: "Initial Request:" and the message content. No `typer.secho("")` call. The trailing blank line was removed in Turns 43-44 as part of a fix for the duplicate issue, but this removal also eliminated the blank line separator between "Session created" and "Initial Request:".

**Bug #3 (CONFIRMED — TUI bypasses SessionOrchestrator entirely):** The `_print_user_message` helper is ONLY called inside `SessionOrchestrator.execute()` at line 323. The TUI execution path (`textual_plan_reviewer_execution.py::_execute_silently`) uses `dispatcher.dispatch_and_execute()` directly — it NEVER goes through `SessionOrchestrator.execute()`. Therefore `_print_user_message` is never invoked for TUI-driven sessions.

Additionally, the `_dispatch_single_action` return value is the `reason` string from `_get_interactive_confirmation`. For MESSAGE actions (communication turns), `_get_interactive_confirmation` is skipped, so `reason` defaults to `""`, meaning `captured_message` is always empty for MESSAGE actions. The TUI sets `plan.metadata["user_request"]` directly in `_finalize_user_message`, but that metadata lives on the TUI's local `Plan` object — it's not processed by the console output layer.

The root cause has two components:
1. **Architectural bypass**: The TUI calls `dispatcher.dispatch_and_execute()` directly instead of going through `SessionOrchestrator.execute()`, so none of the `_print_*` console visibility helpers run.
2. **Missing return propagation**: `confirm_and_dispatch` returns `reason` (always `""` for MESSAGE actions) instead of the user's typed message. Even if the flow went through `SessionOrchestrator`, `captured_message` would be empty for MESSAGE actions.

The fix requires either:
- Option A: Move user message printing into the TUI execution handler (closer to the UI).
- Option B: Wrap `_execute_silently` to emit console visibility output after dispatch.
- Option C: Change `confirm_and_dispatch` to return the actual user message for MESSAGE actions, and ensure the orchestrator path receives it.

**Bug #4 (CONFIRMED, set aside by user):** The `fetch_system_prompt()` method in `prompt_manager.py` searches (1) session root and (2) `.teddy/prompts/` via path traversal. When neither exists, `_find_prompt_file()` returns `None` for each search. These `None` values are then passed to the logger's `%s` formatting, producing "searched None and None". The root cause is that `fetch_system_prompt` does NOT fall back to `find_prompt_content()` from `teddy_executor.prompts`, which is the method that `get_prompt_content()` uses and which traverses from CWD upward to find `.teddy/prompts/`. The actual prompt files live in `src/teddy_executor/resources/config/prompts/` (for bundled resources) or `.teddy/prompts/` (after `teddy init` copies them). The `teddy init` command copies bundled XMLs to `.teddy/prompts/`, but if the project is not initialized or the session is run from a different directory, the path traversal `turn_path.parent.parent.parent.parent / ".teddy" / "prompts"` may point to the wrong location.

**Bug #1 (CONFIRMED):** The `execute()` method in `session_orchestrator.py` calls `_print_initial_request()` at lines 185-188. This call path is reached on EVERY turn via the `elif is_session and plan_path:` branch, which reads `initial_request.md` from disk. There is NO turn_number guard, unlike the lifecycle manager's `_handle_planning_and_execution()` which has `if turn_number == "01":`. The probe confirmed that calling `_print_initial_request(None, True, plan_path=...)` for turn "02" with `initial_request.md` present produces output ("Initial Request:" label and content).

**Bug #2 (CONFIRMED):** The `_print_initial_request` helper in `session_orchestrator.py` does NOT emit a trailing blank line. The probe confirmed exactly 2 calls to `typer.secho`: "Initial Request:" and the message content. No `typer.secho("")` call. The trailing blank line was removed in Turns 43-44 as part of a fix for the duplicate issue, but this removal also eliminated the blank line separator between "Session created" and "Initial Request:".

**Bug #3 (RESOLVED):** The wiring at line 322-323 of `execute()` reads `user_reply = plan.metadata.get("user_request", "")` and passes it to `_print_user_message`. The probe confirmed that when `plan.metadata` contains `"user_request"`, `_print_user_message` correctly outputs "User Message:" and the content. When metadata is empty, no output is produced. The Turns 43-44 fix (reading from metadata instead of the `message` parameter) appears to have resolved this issue. The redundant fallback inside `_print_user_message` (`plan.metadata.get("user_request")`) is harmless.

**Bug #4 (CONFIRMED):** The `fetch_system_prompt()` method in `prompt_manager.py` searches (1) session root and (2) `.teddy/prompts/` via path traversal. When neither exists, `_find_prompt_file()` returns `None` for each search. These `None` values are then passed to the logger's `%s` formatting, producing "searched None and None". The root cause is that `fetch_system_prompt` does NOT fall back to `find_prompt_content()` from `teddy_executor.prompts`, which is the method that `get_prompt_content()` uses and which traverses from CWD upward to find `.teddy/prompts/`. The actual prompt files live in `src/teddy_executor/resources/config/prompts/` (for bundled resources) or `.teddy/prompts/` (after `teddy init` copies them). The `teddy init` command copies bundled XMLs to `.teddy/prompts/`, but if the project is not initialized or the session is run from a different directory, the path traversal `turn_path.parent.parent.parent.parent / ".teddy" / "prompts"` may point to the wrong location.

### Discrepancies
- (resolved: Bug #3 confirmed working via probe - the Turns 43-44 fix resolved the issue.)

### Investigation History
1. Initial context gathering. Read all three source files. Confirmed code exists with potential issues.
2. Created MRE for Bug #4. Reproduced the "searched None and None" warning. Confirmed the root cause: no fallback to `find_prompt_content()`.
3. Read execute() method (lines 175-330) to verify Bug #1 duplicate call path and Bug #3 wiring. Confirmed: execute() calls _print_initial_request without turn_number guard. Confirmed: execute() reads plan.metadata["user_request"] for _print_user_message.
4. Created and executed unified probe for Bugs #1-#3.
   - Bug #1 CONFIRMED: _print_initial_request printed content for turn "02".
   - Bug #2 CONFIRMED: Only 2 calls to typer.secho (missing trailing blank line).
   - Bug #3 RESOLVED: User message correctly printed when metadata populated; empty reply correctly suppressed.
5. Created shadow files for fixes (shadow_prompt_manager.py for Bug #4, shadow_session_orchestrator.py for Bugs #1-#2).
6. Created unified MRE for Bug #4 shadow fix verification.
7. Read ActionExecutor.confirm_and_dispatch. Discovered it returns `reason` (always `""` for MESSAGE) instead of user message.
8. Read textual_plan_reviewer_execution.py and textual_plan_reviewer_app.py. Discovered TUI `_execute_silently` calls dispatcher directly, bypassing SessionOrchestrator entirely — confirming Bug #3 root cause.
9. Systemic Audit: grep for `_execute_silently`, `_dispatch_single_action`, `confirm_and_dispatch` callers to identify similar bypass patterns.

## Solution

### Root Cause Summary

| Bug | Root Cause | Priority |
|-----|------------|----------|
| #1 | `execute()` in session_orchestrator.py calls `_print_initial_request` **without turn_number guard**. The lifecycle manager has `if turn_number == "01":` but the orchestrator's direct call path reads `initial_request.md` every time. | High (every turn shows duplicate) |
| #2 | `_print_initial_request` helper emits only 2 `typer.secho` calls — missing trailing `typer.secho("")`. The blank line was removed in a previous fix. | Medium (cosmetic spacing) |
| #3 | **Twofold cause: (a)** TUI execution path (`_execute_silently`) calls `dispatcher.dispatch_and_execute()` directly, bypassing `SessionOrchestrator.execute()` where `_print_user_message` lives. **(b)** `confirm_and_dispatch` returns `reason` (always `""` for MESSAGE) instead of the user's typed message. | High (user reply never logged) |
| #4 | `fetch_system_prompt` uses fragile path traversal (`turn_path.parent.parent.parent.parent / ".teddy" / "prompts"`) that can miss the file even when it exists. No fallback to `find_prompt_content()`. Logging converts `None` → "None" via `%s`. | Medium (set aside by user) |

### Verified Fixes (Shadow Files)
- **Bugs #1 & #2**: `spikes/debug/shadow_session_orchestrator.py` — adds `_should_print_initial_request()` guard checking `turn_number == "01"` and trailing blank line.
- **Bug #4**: `spikes/debug/shadow_prompt_manager.py` — adds `find_prompt_content()` fallback and descriptive "<not found>" strings instead of "None". All 4 test scenarios passed in `02-unified-mre.py`.

### Preferred Fix Strategy (Bug #3)
1. **Option C** — Fix `confirm_and_dispatch` to return the actual user message (not `reason`) as the second return value for MESSAGE actions.
2. **Wrapping** — Update the TUI execution handler to invoke `_print_user_message` after dispatch, or move user message printing into `ActionDispatcher` itself.

### Preventative Measures
1. **Add centralized guard helper**: Create a shared `_should_print_initial_request(turn_number)` utility that both lifecycle manager and orchestrator call, preventing future duplicate guards.
2. **Standardize output path**: Ensure all console visibility helpers are invoked from a single, consistent execution path (either `SessionOrchestrator` or a common middleware) so the TUI cannot bypass it.
3. **Improve logging defensiveness**: Replace `%s` formatting of potentially-None values with explicit string formatting that handles None gracefully.
