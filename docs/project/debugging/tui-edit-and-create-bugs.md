- **Status:** Resolved

## Failure Context
When modifying the contents of an `EDIT` action within the interactive TUI plan reviewer, the execution fails with a `TypeError`. The user's execution report shows the error: `LocalFileSystemAdapter.edit_file() got an unexpected keyword argument 'content'`.

Additionally, several other related UX issues were reported:
1.  A `PROMPT` action with a message-only parameter incorrectly shows a "have you saved? y/n" confirmation.
2.  The TUI does not display a `*modified` indicator next to actions that have been edited.
3.  Editing a `CREATE` action incorrectly opens editors for both the file path and the content, which can cause deadlocks.

This investigation will prioritize fixing the blocking `TypeError` and then address the other UI/UX issues.

## Steps to Reproduce
1. Launch the interactive TUI reviewer for a plan containing an `EDIT` action.
2. Select the `EDIT` action in the action tree.
3. Press `e` to edit the action's content.
4. The TUI opens an external editor. Make a change and save the file.
5. Confirm the changes in the TUI.
6. Approve the plan for execution.

## Expected vs. Actual Behavior
- **Expected:** The plan executes, and the `EDIT` action successfully modifies the target file based on the changes made in the TUI.
- **Actual:** The execution fails with a `TypeError`, and the `Execution Report` shows `LocalFileSystemAdapter.edit_file() got an unexpected keyword argument 'content'`.

## Relevant Code
*TBD*

## Experiment Log
### Verifying the `edit_file` Method Signature
- *Hypothesis:* The `edit_file` method signature in the `IFileSystemManager` port and its implementation in `LocalFileSystemAdapter` does not accept a `content` keyword argument.
- *Experiment:* Read the design document (`docs/architecture/core/ports/outbound/file_system_manager.md`), the port interface (`src/teddy_executor/core/ports/outbound/file_system_manager.py`), and the adapter implementation (`src/teddy_executor/adapters/outbound/local_file_system_adapter.py`).
- *Observation:* All three sources confirm the method signature is `edit_file(self, path: str, edits: list[dict[str, str]], similarity_threshold: float, match_all: bool) -> list[float]`. No `content` parameter exists.
- *Conclusion:* The hypothesis is validated. The `TypeError` is caused by an incorrect call from a higher-level component, not by a flaw in the `LocalFileSystemAdapter` itself. The investigation must now focus on finding the call site.

### Isolating the TUI Call Site
- *Hypothesis:* The bug originates in `textual_plan_reviewer_logic.py`, where the modified parameters for an `EDIT` action are incorrectly assembled.
- *Experiment:* Read `textual_plan_reviewer_logic.py` and its corresponding tests.
- *Observation:* The `edit_action_logic` function in this file handles `EXECUTE` and `RESEARCH` actions itself but delegates all other types, including `EDIT`, to a `do_preview_logic` function imported from `textual_plan_reviewer_previews.py`.
- *Conclusion:* The hypothesis is falsified. The fault is not in `textual_plan_reviewer_logic.py` but is further down the call stack within the previewing logic. The investigation must now focus on `textual_plan_reviewer_previews.py`.

### Pinpointing the Root Cause
- *Hypothesis:* The bug originates in `textual_plan_reviewer_previews.py`, specifically in the logic that handles the return from an external editor for an `EDIT` action.
- *Experiment:* Read the source code of `src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py`.
- *Observation:* The `preview_edit` function contains the following code block:
  ```python
    if confirmed:
        action.modified = True
        if final is not None and str(final) != str(proposed):
            action.params["content"] = str(final)
        app._refresh_node(node)
  ```
  This block is executed after the user modifies the content of an `EDIT` action in an external editor. It incorrectly adds a `content` key to the action's parameters instead of calculating a diff and populating the `edits` key with a list of find/replace dictionaries.
- *Conclusion:* The hypothesis is validated. This is the verifiable root cause of the `TypeError`.

## Root Cause Analysis
The root cause of the primary bug (`TypeError: edit_file() got an unexpected keyword argument 'content'`) is a logical flaw in the `preview_edit` function within `src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py`.

1.  **Incorrect Parameter Mutation:** When a user edits the content for an `EDIT` action in the TUI, the `preview_edit` function correctly opens an external editor and retrieves the modified content. However, upon confirmation, it mutates the action's parameters by setting `action.params["content"] = modified_content`.
2.  **Contract Violation:** This violates the contract of the `IFileSystemManager.edit_file` method, which the `EDIT` action ultimately calls. The `edit_file` method expects a parameter named `edits`, which should be a list of find/replace dictionaries (`list[dict[str, str]]`), not a `content` string.
3.  **Resulting TypeError:** When the `ActionDispatcher` later attempts to execute this malformed `EDIT` action, it passes the `content` parameter to `edit_file`, which does not recognize it, resulting in the reported `TypeError`.

The secondary bugs are also traced to this file and its interaction patterns:
-   **CREATE action bug:** The `preview_create` function launches both a content editor and a path editor concurrently, leading to a confusing UX and potential deadlocks.
-   **PROMPT action bug:** The `preview_prompt` function reuses the file-editing pattern (`launch_editor` with a confirmation modal), which is inappropriate for a simple message prompt and causes the "have you saved?" dialog to appear.
-   **Missing `*modified` indicator:** The `edit_action_logic` in `textual_plan_reviewer_logic.py` for simple modal edits (like `EXECUTE` commands) sets `action.modified = True` but doesn't call `app._refresh_node(node)` in all cases, failing to update the UI.

## Solution Analysis (Revised)
This section outlines the final implementation strategies for the identified bugs, incorporating user feedback on UI/UX behavior.

### Primary Bug: `EDIT` Action `TypeError` (Verified Fix)
-   **Strategy:** The "Diffing" Strategy.
-   **Status:** Implemented and Verified.
-   **Detail:** In `preview_edit`, modified content is converted into a full-file find/replace block stored in `action.params["edits"]`. The incorrect `content` parameter is removed.

### Secondary UI/UX Bugs (Revised)

1.  **`CREATE` Action Content Editing:**
    -   **Revision:** The `e` key on a `CREATE` action in the tree should *only* trigger the external editor for the content.
    -   **Approach:** Remove the `PathInputScreen` from the `preview_create` logic. Users will edit the path via the parameter list in the right pane (logic to be verified/implemented).

2.  **`PROMPT` Action Behavior:**
    -   **Revision:** The `PROMPT` edit should launch an external editor for the response content, matching the behavior of the `--console` mode.
    -   **Approach:** `preview_prompt` will continue to use `launch_editor` but will discard the redundant `ConfirmScreen`. The closing of the editor is treated as the submission.

3.  **Missing `*modified` Indicator:**
    -   **Revision:** The indicator must appear for *any* action modification.
    -   **Approach:** Ensure `app._refresh_node(node)` is called in all modification paths within `edit_action_logic` and related preview functions, covering all action types.

4.  **`m` (Add Message) Command:**
    -   **Revision:** Remove the "have you saved? y/n" confirmation modal.
    -   **Approach:** Modify `ReviewerApp.action_add_message` to update the message cache immediately upon editor closure.

## Implementation Notes
The following fixes were implemented:
1.  **EDIT Action Fix:** In `preview_edit` (`textual_plan_reviewer_previews.py`), the logic was changed to generate a diff (original vs modified) and store it in `action.params["edits"]`. The erroneous `action.params["content"]` key was removed.
2.  **Submit Harvest Fix:** In `ReviewerApp.action_submit` (`textual_plan_reviewer_app.py`), the harvest logic was updated to skip injecting `content` for `EDIT` actions, preventing accidental `TypeError` regressions.
3.  **CREATE UX Fix:** `preview_create` was refactored to be sequential: Path input first, then Content editor. This prevents concurrent modal deadlocks.
4.  **PROMPT UX Fix:** `preview_prompt` was simplified to remove the redundant `ConfirmScreen`. Closing the external editor now signifies submission intent.
5.  **UI Refresh Fix:** Added explicit `app._refresh_node(node)` calls in `edit_action_logic` to ensure the `*modified` label appears immediately after any modification.
