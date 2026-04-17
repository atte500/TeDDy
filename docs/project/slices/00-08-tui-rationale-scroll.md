# Slice 00-08: TUI Rationale Scrolling via ContentSwitcher

## 1. Metadata
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** N/A
- **Prototype:** [prototypes/tui_ui_integration_spike.py](../../../prototypes/tui_ui_integration_spike.py)
- **Component Docs:** N/A

## 2. Business Goal
Provide a smooth, native scrolling experience for massive, read-only text blocks (like the "Rationale") in the TUI's right panel. This must be accomplished without sacrificing terminal real estate and without breaking the interactive `ListView` parameter editing workflow used for "Action" items.

## 3. Scenarios

> As an AI workflow user,
> I want to seamlessly scroll through large rationale and context blocks in the TUI,
> so that I can read the AI's full reasoning before approving a plan.

**Scenario: Navigating to an Action item**
Given the user is viewing the interactive plan in the TUI
When the user highlights an Action node in the left-hand tree
Then the right panel should display the interactive parameter `ListView`
And the user can click parameters to edit them.

**Scenario: Navigating to a Rationale item**
Given the user is viewing the interactive plan in the TUI
When the user highlights a Rationale node in the left-hand tree
Then the right panel should instantly swap to a scrollable text viewer (e.g., `VerticalScroll` or `Markdown`)
And the user can scroll smoothly through the entire text block natively.

## 4. Deliverables
- [x] **Contract** - Define `ALLOWED_RATIONALE_SECTIONS` constant in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`.
- [ ] **Harness** - Update `TuiDriver` to support `ContentSwitcher` state verification and `Markdown` content inspection.
- [ ] **Logic** - Update `on_mount_logic` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py` to filter rationale sections by `ALLOWED_RATIONALE_SECTIONS` and append non-standard sections to the preceding standard section.
- [ ] **Wiring** - Replace `ParameterDetail` with a `ContentSwitcher` containing both `ParameterDetail` and a `VerticalScroll` in `ReviewerApp.compose`. Preserve `#right-pane` ID for CSS compatibility.
- [ ] **Logic** - Refactor `_update_detail_view` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py` to toggle the `ContentSwitcher` and update the `Markdown` widget for rationales without redundant headers.
- [ ] **Logic** - Update `format_node_label` and `DetailItem` to correctly stringify Enum values (e.g., `ActionType.CREATE` -> `CREATE`).
- [ ] **Cleanup** - Harmonize `VerticalScroll` background with `ListView` using `$surface` in `TUI_CSS`.

## 5. Delta Analysis
- **Current State:** The right panel is a single `ListView` (`ParameterDetail`). Large rationale blocks are split into `ListItem`s, which prevents native scrolling of the entire block and limits the display to plain text.
- **Proposed Change:** Wrap the right panel in a `ContentSwitcher`. One branch remains the `ParameterDetail` (for actions), and the other becomes a `VerticalScroll` containing a `Markdown` widget (for rationales). This allows for rich text rendering and native scrolling.
- **Constraints:** The rationale parser has been validated to correctly filter for "Synthesis", "Justification", "Expectation", and "State Dashboard", ignoring any other H3/list headers.

## 6. Guidelines for Implementation
**For the Prototyper:**
- The current implementation uses a fixed `ListView` for the right pane (`ParameterDetail`).
- Do not attempt to force nested scrolling inside the `ListView`.
- Build a standalone Textual spike (`prototypes/tui_rationale_scroll_spike.py`) that demonstrates the use of a **`ContentSwitcher`**.
- The `ContentSwitcher` should toggle between two child containers:
  1. A dummy `ListView` (representing the Action parameters).
  2. A `VerticalScroll` or `Markdown` widget containing a massive string (representing the Rationale).
- Demonstrate that toggling the left-hand tree correctly flips the `ContentSwitcher` state and that the long text scrolls naturally.

## 7. Implementation Notes
### Deliverable: Contract - Define ALLOWED_RATIONALE_SECTIONS
- Defined the `ALLOWED_RATIONALE_SECTIONS` constant in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`.
- Value: `["Synthesis", "Justification", "Expectation", "State Dashboard"]`.
- Verified existence and values via unit test `tests/suites/unit/adapters/inbound/test_section_filtering.py`.
