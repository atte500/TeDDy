# Slice: Chronological Session History Integration
- **Status:** Draft
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** [link or TBD]
- **Showcase:** N/A
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
- [ ] **Contract** - Define `HISTORY_LABEL = "HISTORY_LABEL"` in `textual_plan_reviewer_logic.py`.
- [ ] **Logic** - Add parsing and chronological sorting logic for `.teddy/sessions/` paths in `ContextService`.
- [ ] **Wiring** - Update `ContextService._format_content` to exclude session history from workspace resource contents and output them in the new `Session History` section.
- [ ] **Wiring** - Update `build_context_section` in `textual_plan_reviewer_helpers.py` to filter out session history files from "Session" and "Turn" lists and place them under a new italicized "History:" node.
- [ ] **Wiring** - Update `refresh_node_logic` and `_is_context_data` to properly style and update details for toggled history items.
- [ ] **Verification** - Add unit tests verifying `ContextService` formatting of session history.
- [ ] **Verification** - Add unit tests/TUI tests verifying correct rendering of the "History:" sub-folder and child labels.
