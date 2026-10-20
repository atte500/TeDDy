# Component Design: TextualPlanReviewer
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/inbound/textual_plan_reviewer.py`](/src/teddy_executor/adapters/inbound/textual_plan_reviewer.py)

## Purpose
Implements the `IPlanReviewer` inbound port with a dual-pane `Textual` TUI. It provides an interactive terminal experience for reviewing, modifying, and selectively executing a plan before it runs. Supporting logic lives in the sibling `textual_plan_reviewer_*.py` modules.

## Consumers
- [`ExecutionOrchestrator`](../../core/services/execution_orchestrator.md): Invokes review through the `IPlanReviewer` port for interactive plans.

## Dependencies
- [`ISystemEnvironment`](../../core/ports/outbound/system_environment.md): Launches the external editor for context-aware editing.
- **`is_cli_editor` / `normalize_editor_basename`** (`teddy_executor.core.utils.editor_names`): Classify editor commands by stripping Windows launcher suffixes and lowercasing the basename. The module-level `_is_cli_editor` in `textual_plan_reviewer_editor.py` stays a thin delegator because `textual_plan_reviewer_previews` imports it.

## Class Invariants
- `stdin_ownership`: While the app runs, the reviewer claims `stdin_owned()` so the session quit-key listener backs off and the TUI's own `q` binding stays authoritative.
- `rationale_dual_format`: The rationale parser accepts both Markdown headings (`### Section`) and numeric markers (`1. Section`), splitting on `\n(?=### |\d+\.\s+)` and stripping the marker from the displayed title.
- `log_is_read_only`: Viewing an action log bypasses the apply-changes confirmation prompt.
- `mutable_plan_models`: The `Plan` and `ActionData` models are unfrozen so the reviewer can update them in memory.

## Inbound Ports
- **`IPlanReviewer`**: Exposes `review(plan, project_context=None)` and `review_action(action, total_actions, agent_name=None)`.

## Outbound Ports
- **`ISystemEnvironment`**: Consumed to open the editor for parameter edits.

## Data Contracts
- **`Plan`** and **`ActionData`** (`teddy_executor.core.domain.models.plan`): The reviewed objects, updated in memory.
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): Optional context metadata shown in the context pane.

## Operations

### `review(plan, project_context=None) -> Optional[Plan]`
- **Preconditions:** `plan` is a valid `Plan`.
- **Postconditions:** Returns the plan carrying the user's selections and edits, or `None` when the user cancels. The dual-pane layout shows a 65% action tree and a 35% parameter detail pane. Selecting the Context root shows an aggregate token breakdown: the `System` line sums the system-prompt and system-info tokens, and the `Total Context` line divides content plus system-prompt tokens by the model window.

### `review_action(action, total_actions, agent_name=None) -> tuple[bool, str]`
- **Postconditions:** Returns `(should_execute, captured_message)` for sequential review.

### Keyboard bindings
`s` submits the plan; `a` toggles all actions; `e` edits the highlighted action (external editor for CREATE and EDIT, modal for EXECUTE and RESEARCH); `d` opens the read-only action log; `r` reverts manual modifications; `v` views the original plan file; `x` marks a step executed; `m` adds or edits a user message; `q` cancels and exits.

### Action log format
The reviewer renders an action log as a structured Markdown document: an `### {ACTION_TYPE}: {SUMMARY}` header, a `- **Status:** {STATUS}` line, and quadruple-backtick fences around `stdout`, `stderr`, and `diff`.
