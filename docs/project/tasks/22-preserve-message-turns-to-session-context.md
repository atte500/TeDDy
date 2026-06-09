# Task: Save Message & User-Request Turns to `session.context`

## Business Goal
When `preserve_message_turns: true`, message turns (plans containing `## Message`) and user-request turns (reports containing `- **User Request:**`) should have their `plan.md` and `report.md` artifacts appended to `session.context` (Session scope) instead of `turn.context` (Turn scope). This naturally excludes them from the `turn_context_threshold` budget calculation, eliminating the need for special sparing logic in the pruning service.

## Context
Currently, `SessionService.transition_to_next_turn()` always appends `plan.md` and `report.md` of the current turn to the **next turn's `turn.context`**. The `SessionPruningService` then uses complex sparing logic to protect message turns and user-request turns from being pruned — checking `## Message` in plan files and `- **User Request:**` in report files, maintaining a `spared_turns` set, and propagating it through retention and budget heuristics.

The solution moves message/user-request artifacts to `session.context` (which is already excluded from the `turn_context_threshold` calculation at the pruning stage), allowing complete removal of the sparing logic from the pruning service. `session.context` is a session-level file at `<session_root>/session.context`.

**Key insight:** Session-scope files are already excluded from the budget calculation in `SessionPruningService._apply_global_budget()` via the `item.scope == "Turn"` filter. By placing message turn artifacts in Session scope, they are naturally protected without any special-casing.

### Detection: Two Turn Types to Guard
1. **Message turns:** The turn's `plan.md` contains `## Message` (indicating a pure communication turn).
2. **User-request turns:** The turn's `report.md` contains `- **User Request:**` (indicating the user provided an additional message during review of an action plan).

When `preserve_message_turns: true` (the default), BOTH types should have their artifacts saved to `session.context` instead of `turn.context`.

## Implementation Steps

### Step 1: Add session context writing to `transition_to_next_turn`
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Modify `transition_to_next_turn` to detect message turns and user-request turns, and conditionally write artifacts to `session.context` instead of `turn.context`.

**Details:**
1. Add a helper method `_is_preserved_turn(cur_dir: Path) -> bool` that:
   - Reads `cur_dir/plan.md` and checks for `^## Message` (using regex `re.MULTILINE`)
   - Reads `cur_dir/report.md` (if exists) and checks for `^- \*\*User Request:\*\*` (using regex `re.MULTILINE`)
   - Returns `True` if either pattern matches
   - Caches file reads to avoid unnecessary I/O
2. In `transition_to_next_turn`, after the `# 4. Handle context` section, before writing to `turn.context`:
   - Read the config setting `auto_pruning.preserve_message_turns` via `config_service.get_setting()`
   - If enabled AND `_is_preserved_turn(cur_dir)` returns True:
     - Instead of adding `plan.md` and `report.md` paths to the `paths` set (which gets written to `turn.context`), append them to `session.context`
     - The session context path is `<session_root>/session.context` (where `session_root` is the parent of `cur_dir`)
     - Read the existing session context, add the paths if not present, write back
   - If not enabled or not a preserved turn, proceed as before (append to turn.context)
3. The existing `_apply_execution_effects` should still run for message turns — the action effects (READ/CREATE/EDIT paths) should still go to `turn.context` even if the turn metadata goes to `session.context`. This keeps the semantic distinction: turn working set in `turn.context`, turn history markers in `session.context`.

**Important:** `transition_to_next_turn` currently does not have access to `config_service`. The method is called from `SessionLifecycleManager.finalize_turn`. Add `config_service` as a dependency to `SessionService.__init__` (via constructor injection) and update the `container.py` wiring. Alternatively, pass the `preserve_message_turns` flag as an optional parameter to `transition_to_next_turn` with default `True`.

### Step 2: Remove sparing logic from `SessionPruningService`
- **File:** [src/teddy_executor/core/services/session_pruning_service.py](/src/teddy_executor/core/services/session_pruning_service.py)
- **Change:** Delete all message turn and user-request sparing logic.

**Specific removals:**
1. Remove method `_check_plan_is_message(self, path: str) -> bool`
2. Remove method `_check_report_has_user_request(self, path: str) -> bool`
3. Remove method `_check_report_is_success(self, path: str) -> bool` (only used by message sparing)
4. In `_identify_turns_to_prune`:
   - Remove the `preserve_messages` config read
   - Remove the `spared_turns` return value (change return type from `tuple[Dict[str, str], set[int]]` to `Dict[str, str]`)
   - Remove the block `if preserve_messages: for tid in spared_turns: turns_to_prune.pop(str(tid), None)`
5. In `_collect_turn_metadata`:
   - Remove the `preserve_messages` parameter
   - Remove the `spared_turns` set creation and return
   - Remove the lines that update `spared_turns` (both from `_update_metadata_from_report` and `_update_metadata_from_plan`)
   - Remove the `_update_metadata_from_plan` method entirely (it only handled message sparing) — or simplify to only track statuses and validation failures
   - Simplify `_update_turn_metadata_from_item` accordingly
6. Update all callers of these methods within the class to match the new signatures
7. In `_apply_retention_limit` and `_apply_global_budget`, remove the `spared_turns`/`spared_ids` parameter and all related skipping logic
8. In `prune()` method, remove the `spared_turns` variable propagation

### Step 3: Update `SessionService.__init__` to accept `config_service`
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Add `config_service: IConfigService` to the constructor parameters and store as `self._config_service`.

### Step 4: Update container wiring
- **File:** [src/teddy_executor/container.py](/src/teddy_executor/container.py)
- **Change:** Ensure `SessionService` receives `config_service` in its constructor wiring.

### Step 5: Remove or update pruning service tests for message sparing
- **Files:**
  - [tests/suites/unit/core/services/test_session_pruning_message_protection.py](/tests/suites/unit/core/services/test_session_pruning_message_protection.py)
  - [tests/suites/unit/core/services/test_session_pruning_preserve_messages_budget.py](/tests/suites/unit/core/services/test_session_pruning_preserve_user_requests.py)
- **Change:** Remove test files that specifically test the old sparing logic, or update them to reflect the new behavior (session.context instead of sparing).

**Details:**
- `test_session_pruning_message_protection.py` — tests for `_check_plan_is_message` and sparing of message turns. These tests should be removed or adapted to verify that message turn artifacts are NOT in turn.context (since they now live in session.context).
- `test_session_pruning_preserve_messages_budget.py` — tests for budget sparing of message turns. Remove or adapt.
- `test_session_pruning_preserve_user_requests.py` — tests for user request sparing. Remove or adapt.

A pragmatic approach: remove the dedicated sparing test files and instead add a few assertions in existing `session_service` tests (e.g., `test_session_service.py` or `test_session_service_transition.py`) to verify that preserved turn artifacts go to `session.context` rather than `turn.context`.

### Step 6: Update session service tests
- **File:** [tests/suites/unit/core/services/test_session_service_transition.py](/tests/suites/unit/core/services/test_session_service_transition.py) (or similar)
- **Change:** Add tests verifying:
  1. A message turn (`plan.md` with `## Message`) appends `plan.md` and `report.md` to `session.context`, not `turn.context`
  2. A user-request turn (`report.md` with `- **User Request:**`) appends artifacts to `session.context`
  3. A normal action turn (no message, no user request) continues to append to `turn.context`
  4. The `preserve_message_turns: false` config restores old behavior (append to `turn.context`)
  5. The `_apply_execution_effects` still runs for message turns (READ/CREATE/EDIT effects still go to `turn.context`)
  6. Session context deduplication works (same path not added twice)

## Verification
1. All unit tests pass (`poetry run pytest tests/suites/unit/ -x -q`)
2. All pruning service tests pass (after updating/removing sparing-specific tests)
3. All integration tests pass (`poetry run pytest tests/suites/integration/ -x -q`)
4. Manual verification: Start a session, generate a message turn, inspect `<session>/session.context` — should contain the `plan.md` and `report.md` paths from the message turn
5. Manual verification: Start a session with an action plan, provide an additional user message during review, inspect `<session>/session.context` — should contain the `report.md` path with the `- **User Request:**` header
6. Regression: Normal action turns without user messages still have their `plan.md`/`report.md` in `turn.context` as before
7. Regression: Session migration (turn 99 → continuation session) still carries over `session.context` correctly
