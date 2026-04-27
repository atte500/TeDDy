# Task Brief: TUI Polish & Workflow Improvements

## Objective
Enhance the Textual Plan Reviewer (TUI) with three specific quality-of-life improvements.

## Implementation Guidelines

### 1. Intercept Quit (`q`) to Prompt for Message
**Target:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`

Modify `action_cancel` to be an `async` method:
1. Retain the existing loop that cleans up `action.pending_temp_file`.
2. Check if `self.plan.session_message` is empty (`not self.plan.session_message`).
3. If empty, await `add_message_handler(self)` (import this from `teddy_executor.adapters.inbound.textual_plan_reviewer_previews`).
4. **After the prompt**, re-check `self.plan.session_message`.
5. If it now contains text:
   - Iterate through `self.plan.actions` and explicitly set `action.selected = False` for all actions.
   - Call `self.exit(self.plan)` to return the plan to the orchestrator. This logs the message in the execution report and proceeds to the next turn without executing any actions.
6. If it remains empty (user canceled the message prompt or left it blank):
   - Call `self.exit(None)` to break the session loop (existing behavior).

### 2. Rename 'e' Binding
**Target:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`
- In the `BINDINGS` list, update the description for the `"e"` key from `"Edit/Preview"` to `"Editor"`.

### 3. Fix Shift + Up/Down Navigation
**Target:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py` & `src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py`

- **ActionTree (Left Pane):** Ensure `ActionTree.jump_to_section` correctly jumps to the `RATIONALE_ROOT` or `ACTION_PLAN_ROOT`, even if focus is currently deep within a child node. Currently, `self.move_cursor(child)` might fail to reset the tree state if not at the root level.
- **ParameterDetail (Right Pane):** Add explicit action handlers and bindings for `shift+up` and `shift+down` within `ParameterDetail` (a `ListView`). Pressing these should jump focus directly to the very top (index 0) or the very bottom (index `len(self.children) - 1`) of the parameter list.

## Out of Scope
- "Undo" session rollback functionality. This requires systemic changes to the SessionService and will be handled as a separate CLI feature (e.g., `teddy session undo`) in the future.

## Verification
- Run `poetry run pytest tests/unit/adapters/inbound/` to ensure all existing TUI unit tests continue to pass.
