**Status:** Implemented

## 1. Purpose / Responsibility
Implements the `IPlanReviewer` port using the `Textual` TUI framework. It provides a rich, interactive terminal experience for reviewing and modifying plans.

## 2. Ports
- **Implements Inbound Port:** `IPlanReviewer`
- **Uses Outbound Ports:**
  - `ISystemEnvironment`: For launching external editors for "Context-Aware Editing".

## 3. Implementation Details / Logic
1. **App Structure:** A `textual.app.App` using a **dual-pane layout** for optimal information density:
   - **Left Pane (ActionTree):** A 65% width tree displaying a flat list of actions (leaf nodes) organized under virtual roots (Rationale, Action Plan).
   - **Right Pane (ParameterDetail):** A 35% width list view that dynamically displays all parameters (including system defaults) for the highlighted action.
2. **Rationale Parsing Protocol:** The `ActionTree` parses the `Plan.rationale` into sections. It MUST support both legacy Markdown headings (`### Section`) and numeric list markers (`1. Section`) at the start of a line.
   - **Split Regex:** `\n(?=### |\d+\.\s+)`
   - **Title Extraction:** Markers (`### ` or `1. `) MUST be stripped from the title displayed in the tree leaf.
3. **Initialization Behavior:** To ensure a useful initial state, the TUI MUST:
   - Highlight the "Rationale" virtual root in the `ActionTree` using `tree.move_cursor()`.
   - Populate the `ParameterDetail` pane with the plan's metadata (Agent, Plan Type, Status) immediately upon mount. This update SHOULD be scheduled after the initial refresh to avoid race conditions with tree events.
4. **Action Log Formatting Contract:** When viewing execution logs (hotkey `d`), the TUI MUST format the `ActionLog` as a structured Markdown document:
   - **Header:** `### {ACTION_TYPE}: {SUMMARY}`
   - **Status:** `- **Status:** {STATUS}`
   - **Fenced Blocks:** `stdout`, `stderr`, and `diff` MUST be wrapped in triple-backtick fences with appropriate language markers (`text` or `diff`).
   - **UX:** Viewing the log is a read-only operation and MUST bypass the "apply changes" confirmation prompt.
5. **Tiered Interaction:**
   - **Tier 1:** Summary view (Header/Footer).
   - **Tier 2:** Detail view/Checklist (Tree) with side-by-side parameter inspection.
3. **Focus Management:** Navigation between panes is handled via `Tab`. Tabbing into the right pane automatically highlights the first parameter.
3. **Modification Logic:**
   - When a user selects "Modify/Preview" (key `p`), the adapter uses the `ISystemEnvironment` to open a temporary file in the user's editor.
   - Upon editor close, the adapter parses the temporary file (or uses the returned path) to update the `ActionData` in-memory.
4. **Return Path:** The `app.run()` call returns the final `Plan` object.

## 4. Data Contracts / Methods
Refer to the [IPlanReviewer](/docs/architecture/core/ports/inbound/plan_reviewer.md) port for method signatures.

### Implementation Notes:
- **Refactoring Requirement:** The `Plan` and `ActionData` models must be unfrozen to support direct in-memory updates by the TUI.
- **Keyboard Bindings:**
  - `s`: Submit the plan and return the results.
  - `a`: Toggle selection for all actions.
  - `e`: Edit (Context-Aware Editing).
    - **CREATE:** Launches the external editor for content, followed by a `PathInputScreen` modal for path adjustment and a `ConfirmScreen`.
    - **EDIT:** Launches the external editor showing the proposed final state (simulated), followed by a `ConfirmScreen`.
    - **EXECUTE/RESEARCH:** Uses a `ParameterEditModal` for simple value changes.
  - `d`: View Details (Action Log). Launches the external editor with a read-only Markdown summary of the action's execution log. Bypasses confirmation.
  - `r`: Revert manual modifications (conditionally enabled).
  - `v`: View the original plan file (read-only).
  - `x`: Execute Step (marks the action as executed/successful).
  - `m`: Add/Edit User Message (Instruction Bridge).
  - `q`: Cancel and exit.
