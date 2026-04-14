# Slice 10: TUI Section Navigation (Rationale <-> Action Plan)

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](../specs/interactive-session-workflow.md)
- **Prototype:** [prototypes/tui_section_nav_spike.py](/prototypes/tui_section_nav_spike.py)
- **Component Docs:** [textual_plan_reviewer](../architecture/adapters/inbound/textual_plan_reviewer.md)

## Business Goal

Improve the efficiency of the TUI by allowing users to quickly jump between high-level sections (Rationale and Action Plan) without manually scrolling through many individual actions or long rationales.

## Scenarios

> As a developer reviewing a plan, I want to jump directly between the AI's explanation and the list of actions so I can quickly correlate intent with implementation.

### Scenario 1: Navigate to Action Plan
- Given I am in the TUI reviewing a plan with a long rationale
- When I press `Ctrl+Down`, `Alt+Down`, or `Shift+Down`
- Then the focus jumps to the first action in the Action Plan tree

### Scenario 2: Navigate back to Rationale
- Given I am in the Action Plan tree
- When I press `Ctrl+Up` or `Alt+Up`
- Then the focus jumps back to the Rationale text area

### Deliverables
- [x] **Contract** - Define `jump_to_section(section_id)` interface in `TextualPlanReviewer`.
- [x] **Harness** - Create `prototypes/tui_section_nav_spike.py` to test focus management between disparate widgets.
- [x] **Logic** - Implement section focus-finding logic in `textual_plan_reviewer_app.py`.
- [x] **Wiring** - Bind `ctrl+up/down` and `alt+up/down` in `ReviewerApp`.

## Guidelines for Implementation

- Both sections are implemented as top-level nodes in the `ActionTree`.
- Rationale Root data: `"RATIONALE_ROOT"`
- Action Plan Root data: `"ACTION_PLAN_ROOT"`
- Navigation should iterate over `tree.root.children` to find the target node and use `tree.move_cursor(node)` to jump.
- Support both `ctrl+up/down` and `alt+up/down` for maximum compatibility.
- Use `app.set_focus()` to move between them.
- Ensure the scroll position is handled gracefully (Textual usually handles this if the widget is focused).
- Consider if "Parameters" or "Details" pane should be a target or if it's strictly a Rationale/Action Plan jump.

## Delta Analysis

### 1. Inbound Adapter (`ReviewerApp`)
- **Key Bindings:** Added `ctrl+down,alt+down,shift+down` and `ctrl+up,alt+up,shift+up` to `BINDINGS`. This provides maximum compatibility across OS/Terminal configurations (notably macOS which intercepts Ctrl+Arrows).
- **Actions:** Implemented `action_jump_next` and `action_jump_prev`.
- **Logic:** These actions perform a linear search of the `ActionTree.root.children` for nodes with `data` matching `ACTION_PLAN_ROOT` or `RATIONALE_ROOT`.
- **Focus Management:** Uses `tree.move_cursor(child)` to navigate and `tree.focus()` to ensure the tree remains the active control.

### 2. UI Consistency
- The navigation skips sub-nodes (Rationale sections or individual actions) and jumps directly to the major section headers.
- This pattern is consistent with "Section Navigation" found in IDEs and document readers.

## Implementation Notes
- **Focus Management:** Navigation is performed on the `ActionTree` by iterating over the top-level children of the hidden root. The `move_cursor` method is used to reposition the focus, followed by an explicit `tree.focus()` call in the app action handlers to ensure the keyboard focus remains on the tree.
- **Cross-Platform Compatibility:** macOS often intercepts `Ctrl+Arrow` keys for mission control. To provide a robust experience, three sets of modifiers were bound: `Ctrl`, `Alt`, and `Shift`.
- **Validation:** Both Unit (widget level) and Acceptance (app/pilot level) tests were implemented to verify the wiring and the logic independently.
