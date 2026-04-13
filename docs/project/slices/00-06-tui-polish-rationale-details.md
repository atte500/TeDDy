# Vertical Slice: TUI Polish (Rationale & Details)

## Metadata
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config.md](../milestones/10-interactive-session-and-config.md)
- **Prototype:** [prototypes/tui_polish_spike.py]
- **Component Docs:** [textual_plan_reviewer.md](../../architecture/adapters/inbound/textual_plan_reviewer.md)

## Business Goal
Improve the TUI user experience by adopting a more robust rationale format, ensuring the UI initializes in a useful state, and aligning the "Action Log" view with the final execution report format.

## Scenarios

### Scenario 1: Robust Rationale Parsing
> As a user, I want the TUI to parse rationale sections formatted as "1. Section" so that I don't have to use Markdown headings in the rationale block.

- [ ] **Harness** - Update `MarkdownPlanBuilder` to generate rationale without `###` headings.
- [ ] **Logic** - Update `on_mount_logic` regex in `textual_plan_reviewer_logic.py` to `r"\n(?=### |\d+\.\s+)"`.
- [ ] **Logic** - Update the title extraction regex to `r"^(###\s*|\d+\.\s*)"`.

### Scenario 2: Right Panel Initialization
> As a user, I want the right panel to show the plan's metadata (Rationale root) immediately upon launch so that I don't see a generic placeholder.

- [ ] **Logic** - Update `on_mount_logic` to explicitly set `tree.cursor_node = rat_root` before calling `_update_detail_view`.

### Scenario 3: Action Log Formatting
> As a user, I want the "Action Log" view (triggered by 'd') to match the format of the final Execution Report so that the experience is consistent.

- [ ] **Contract** - Implement `format_action_log(log: ActionLog) -> str` in `textual_plan_reviewer_helpers.py` to replicate the Jinja2 `render_action_details` macro.
- [ ] **Logic** - Update `action_view_details` in `textual_plan_reviewer_app.py` to use the new formatter.
- [ ] **Wiring** - Add a `skip_confirm: bool = False` parameter to `launch_editor` and `_confirm_and_harvest` in `textual_plan_reviewer_previews.py`.
- [ ] **Wiring** - Pass `skip_confirm=True` when calling `launch_editor` from `action_view_details`.

## Delta Analysis

### Rationale Parsing
The current implementation in `on_mount_logic` (textual_plan_reviewer_logic.py) uses `re.split(r"\n(?=### )", ...)`. The prototype successfully demonstrated that changing this to `re.split(r"\n(?=### |\d+\.\s+)", ...)` enables support for numeric lists. Additionally, the title extraction logic needs to be updated to `re.sub(r"^(###\s*|\d+\.\s*)", "", lines[0]).strip()` to handle both formats.

### Initialization Race Condition
The placeholder message "Select an item to view details" appears initially because `_update_detail_view` is called before the tree has fully settled its state, and subsequent internal tree events (like a root highlight) may overwrite it with empty data.
- **Fix 1:** Use `tree.move_cursor(rat_root)` (not `cursor_node` property) to ensure the visual highlight matches the metadata view.
- **Fix 2:** Use `app.call_after_refresh(_update_detail_view, app, "RATIONALE_ROOT")` to ensure the metadata update is the final initialization step.

### Action Log Formatting
The current `action_view_details` constructs a primitive string.
- **Integration:** Move the `format_action_log` logic from the spike into `textual_plan_reviewer_helpers.py`. This function should replicate the structured Markdown output of the Jinja2 `render_action_details` macro (Outcome, Failed Command, Return Code, Fenced Stdout/Stderr/Diff).
- **UX:** Implement `view_text_readonly` in `textual_plan_reviewer_previews.py` using `app.suspend()` and blocking process execution.
- **Format:** Use `.md` extension for logs to ensure syntax highlighting in the editor.
- **Wait Logic:** Update `ConsoleToolingHelper` to automatically add the `--wait` flag to VS Code (`code`) if no flags are present, ensuring the TUI blocks until the editor window is closed.

## Guidelines for Implementation
- **Rationale Parsing**: The updated regex must use a positive lookahead `(?=...)` to split between sections without consuming the markers.
- **Initialization**: Textual's `Tree` doesn't automatically highlight the first visible node when `show_root=False`. Explicitly setting `cursor_node` ensures the highlighted state matches the `ParameterDetail` view.
- **Action Log Formatter**:
    - Use `### `OUTCOME`: {log.status}` as the header.
    - Include `Failed Command`, `Return Code`, `stdout`, `stderr`, and `diff` sections with appropriate Markdown fencing (````text`` or ````diff``).
    - Ensure `stderr` is only shown if it contains content.
- **Confirmation Bypass**: Ensure `_confirm_and_harvest` defaults `confirmed = True` when `skip_confirm` is set, bypassing the `ConfirmScreen` modal.
