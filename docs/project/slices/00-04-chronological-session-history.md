# Slice: Chronological Session History Integration
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** [spikes/prototypes/00-04-session-history-prototype.py](/spikes/prototypes/00-04-session-history-prototype.py)
- **Showcase:** [spikes/prototypes/00-04-session-history-prototype.py](/spikes/prototypes/00-04-session-history-prototype.py)
- **Component Docs:** N/A

## Business Goal
To isolate the stateful conversation history from normal codebase context, formatting it chronologically and conceptually for LLM consumption, while presenting it as a distinct "History:" sub-folder under the "Context" node in the TUI sidebar to avoid filesystem clutter and protect internal session files from accidental edits.

## Scenarios

### Scenario 1: Formatting chronological session history for the context payload
> As an AI coding agent, I want to read the session history sorted chronologically under a dedicated header so that I can easily understand the dialogue progression without getting confused by long filesystem paths.

```gherkin
Given a session named "20260521_134944-test-session" with:
  | Path                                                   | Content                         |
  | .teddy/sessions/20260521_134944-test-session/initial_request.md | "Implement user login"          |
  | .teddy/sessions/20260521_134944-test-session/01/plan.md          | "Plan for step 1"               |
  | .teddy/sessions/20260521_134944-test-session/01/report.md        | "Report for step 1"             |
When the ContextService gathers the project context with these session files
Then the resulting context payload MUST NOT contain the session files in "## 4. Resource Contents"
And the resulting context payload MUST contain a "## 5. Session History" section at the end
And the "Session History" section MUST contain the files in the following exact order:
  | Section Header              | Expected Content      |
  | ### Initial Request         | "Implement user login"|
  | ### Turn 1: Plan            | "Plan for step 1"     |
  | ### Turn 1: Execution Report| "Report for step 1"   |
And the "Session History" section MUST NOT contain any raw filesystem paths or links to ".teddy/sessions/"
```

### Scenario 2: Displaying session history in the Textual TUI
> As a developer reviewing a plan, I want to see previous turn logs grouped under a "History:" folder in the Context tree so that they do not clutter the "Session:" or "Turn:" workspace file lists.

```gherkin
Given a plan loaded in the Textual Plan Reviewer
And the project context contains session history files for "Initial Request" and "Turn 1"
When the reviewer app is mounted and renders the sidebar ActionTree
Then the "Context" root node MUST NOT list ".teddy/sessions/" files under "Session:" or "Turn:"
And the "Context" root node MUST contain an italic "History:" sub-folder node
And the "History:" folder MUST display the following child nodes in order with their token counts:
  | Node Label                   |
  | Initial Request              |
  | Turn 1: Plan                 |
  | Turn 1: Execution Report     |
```

### Scenario 3: Toggling selection of session history items in the TUI
> As a developer, I want to toggle session history items in the "History:" folder using the spacebar so that I can prune older conversation turns from the active context.

```gherkin
Given the Textual Plan Reviewer is open with "Turn 1: Plan" highlighted under the "History:" folder
When the user presses the [space] key
Then the "Turn 1: Plan" item's selected state MUST toggle
And the tree node label MUST refresh to reflect the updated selection (dimmed if deselected, bold if selected)
And the right-pane ParameterDetail aggregate totals MUST update immediately to exclude or include the item's token count
```

## Edge Cases
- **[No Session History]**: If the active plan is not running in Session Mode, then the `## 5. Session History` section must be omitted from the context payload, in order to maintain backwards compatibility with non-session CLI executions.
- **[Missing Intermediary Files]**: If a turn contains a `plan.md` but is aborted before creating `report.md`, then the sorting algorithm must still cleanly present the `plan.md` under its turn number, in order to prevent crashes from incomplete transitions.
- **[Unrecognized Session Files]**: If the `.teddy/sessions/` directory contains files other than `initial_request.md`, `plan.md`, or `report.md` (e.g. metadata yaml), then those files must be excluded from the "Session History" section, because they are not readable conversation turns.

## Deliverables
- [ ] **Contract** - Define pure helpers (`is_session_file_path`, `is_session_history_path`, `get_session_history_display_name`, `get_session_history_sort_key`) in `src/teddy_executor/core/utils/markdown.py`.
- [ ] **Contract** - Define `HISTORY_LABEL = "HISTORY_LABEL"` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`.
- [ ] **Logic** - Update `ContextService._format_content` to partition workspace files from session files, formatting workspace files in `## 4. Resource Contents` and session files in `## 5. Session History` (sorted chronologically and filtered for recognized turns).
- [ ] **Wiring** - Update `build_context_section` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py` to use the helpers, filtering out all `.teddy/sessions/` files from "Session" and "Turn" lists and rendering recognized history turns under a new italicized `History:` node using `HISTORY_LABEL`.
- [ ] **Wiring** - Update `_is_context_data` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py` to accept `HISTORY_LABEL`.
- [ ] **Wiring** - Update `populate_context_detail` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py` to add a separate `• History` row, summing up selected history items, and only count non-session files in `• Session` and `• Turn` rows.
- [ ] **Verification** - Add unit tests in `tests/suites/unit/core/services/test_context_service.py` to verify chronological formatting, exclusion from `## 4`, inclusion in `## 5`, and backward compatibility.
- [ ] **Verification** - Add unit tests in `tests/suites/unit/adapters/inbound/test_reviewer_app_context_previews.py` (or similar TUI unit tests) to verify TUI `History:` rendering, styling, and aggregate updates on toggling.

## Delta Analysis

We analyzed the verified prototype (`spikes/prototypes/00-04-session-history-prototype.py`) against the codebase:

### 1. `src/teddy_executor/core/utils/markdown.py`
- **Current State**: Contains generic markdown utilities like `get_language_from_path` and `get_fence_for_content`.
- **Delta**: We will add the pure helpers here to ensure they are accessible by both core services and inbound adapters without violating hexagonal boundaries:
  - `get_session_history_display_name(path: str) -> Optional[str]`
  - `is_session_file_path(path: str) -> bool`
  - `is_session_history_path(path: str) -> bool`
  - `get_session_history_sort_key(path: str) -> tuple[int, int]`

### 2. `src/teddy_executor/core/services/context_service.py`
- **Current State**: Gathers all resolved paths, reads their contents, and formats all of them under `## 4. Resource Contents` using `_format_content()`.
- **Delta**:
  - Partition all unique paths into workspace paths (non-session) and session paths (using `is_session_file_path()`).
  - Only format workspace paths in `## 4. Resource Contents`.
  - Format recognized session history paths chronologically (using `get_session_history_sort_key()` and `get_session_history_display_name()`) in a new section `## 5. Session History`.
  - Do not include unrecognized session files (like `.context` or `meta.yaml`) in `## 5. Session History`.

### 3. `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`
- **Current State**: Defines tree root constants. `_is_context_data` checks against `CONTEXT_ROOT`, `SYSTEM_LABEL`, `SESSION_LABEL`, `TURN_LABEL`.
- **Delta**:
  - Add constant `HISTORY_LABEL = "HISTORY_LABEL"`.
  - Include `HISTORY_LABEL` in `_is_context_data()`.

### 4. `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`
- **Current State**:
  - `format_context_item_label` formats node labels using the full path.
  - `build_context_section` loops over all items and puts them under `Session:` or `Turn:` based strictly on `item.scope`.
  - `populate_context_detail` aggregates totals under `• Session` and `• Turn`.
- **Delta**:
  - Update `format_context_item_label` to use clean display names for history items.
  - Update `build_context_section` to filter out any session file from standard folders using `is_session_file_path()`, and add a separate `History:` node listing sorted history items.
  - Update `populate_context_detail` to sum selected history items under a separate `• History` row, and filter out session files from `• Session` and `• Turn` rows.

## Guidelines for Implementation

The Developer should follow the **Deliverable Dependency Sequence** and leverage strict **Test-Driven Development (TDD)** to ensure high fidelity:

### Step 1: Core Path Helpers (TDD)
- Open `tests/suites/unit/core/utils/test_markdown_utils.py` and write tests verifying that:
  - `.teddy/sessions/XYZ/initial_request.md` resolves to `"Initial Request"`.
  - `.teddy/sessions/XYZ/01/plan.md` resolves to `"Turn 1: Plan"`.
  - `.teddy/sessions/XYZ/01/report.md` resolves to `"Turn 1: Execution Report"`.
  - Unrecognized paths resolve to `None`.
  - Sorting keys are correct: Turn 0 (Initial Request) < Turn 1: Plan < Turn 1: Report < Turn 2: Plan.
- Implement these helpers in `src/teddy_executor/core/utils/markdown.py` until all tests pass.

### Step 2: ContextService Format Separation (TDD)
- Open `tests/suites/unit/core/services/test_context_service.py` and add assertions:
  - Verify that when gathering context with session history files, they are omitted from `## 4. Resource Contents` but formatted correctly in `## 5. Session History` at the end.
  - Verify that raw session folder paths like `.teddy/sessions/` do not appear anywhere in `## 5. Session History`.
  - Verify that if no session history files are gathered, `## 5. Session History` is omitted.
- Implement the partitioning and chronological formatting logic in `src/teddy_executor/core/services/context_service.py` until all tests pass.

### Step 3: TUI Node Constant & Aggregates
- Define `HISTORY_LABEL = "HISTORY_LABEL"` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`.
- Include it in `_is_context_data` check.
- In `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`, update `format_context_item_label`, `build_context_section`, and `populate_context_detail` to render the separate chronological `History:` node and update right-pane aggregate totals.

### Step 4: TUI Verification (TDD)
- Open TUI unit tests (such as `tests/suites/unit/adapters/inbound/test_reviewer_app_context_previews.py` or `tests/suites/unit/adapters/inbound/test_reviewer_widgets.py`) and write tests using the mock app and tree:
  - Verify `.teddy/sessions/` files are excluded from Session/Turn lists.
  - Verify the italicized `History:` node is present.
  - Verify the items inside `History:` list chronological display names and their correct token sizes.
  - Verify aggregate totals dynamically update and exclude/include selected history items when they are toggled.
- Ensure all TUI tests pass.

---
## Implementation Notes
*To be filled by the Developer during implementation.*
