# Slice 00-08: TUI Rationale Scrolling via ContentSwitcher

## 1. Metadata
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** N/A
- **Prototype:** [To be created by Prototyper]
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
*To be filled by the Pathfinder after prototype validation.*

## 5. Delta Analysis
*To be filled by the Prototyper/Pathfinder based on prototype findings.*

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
*To be filled by the Developer.*
