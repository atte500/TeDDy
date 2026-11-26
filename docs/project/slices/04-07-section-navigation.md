# Slice: Boundary-Aware Section Navigation
- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `section-navigation`

## Goal
Make Alt+Up/Down walk the whole tree, context subsections included, and stop wrapping at the boundaries so navigation never teleports the cursor from the last action back to the top of the plan.

## Context
- `ReviewerApp.action_jump_next`: Holds a hardcoded three-root list (`CONTEXT_ROOT`, `RATIONALE_ROOT`, `ACTION_PLAN_ROOT`) and advances with `(current_idx + 1) % len(sections)`, so the last section wraps to the first.
- `ReviewerApp.action_jump_prev`: Symmetric, wrapping backwards with `(current_idx - 1) % len(sections)`, and jumping to the current section root when the cursor sits on a child.
- `ActionTree` (`textual_plan_reviewer_widgets.py`): Re-binds `alt+up`, `alt+down`, `ctrl+up`, `ctrl+down`, `shift+up`, and `shift+down` with `priority=True` and forwards them to `app.jump_next` / `app.jump_prev`, so the tree owns the keys whenever it holds focus.
- `ActionTree.jump_to_section`: Searches only the direct children of the invisible root, so nothing below a section root is addressable and a context subsection cannot be a jump target.
- `build_context_section` (`textual_plan_reviewer_helpers.py`): Creates the leaves `System:`, one agent leaf, `Session:`, the session items, `Turn:`, the turn items, and `History:` plus its items only when history entries exist. Each carries a sentinel (`SYSTEM_LABEL`, `SESSION_LABEL`, `TURN_LABEL`, `HISTORY_LABEL`) or a `ContextItem`.
- `RationaleDetail` and `ParameterDetail`: Bind the same key combinations to pane-local `scroll_to_top` / `scroll_to_bottom`, so the right pane keeps its own scroll meaning and stays out of scope.
- `docs/project/specs/interactive-session-workflow.md`, Alt + Up/Down: Fixes the target — jump between major sections, never loop at the boundaries, and instead scroll to the absolute top or bottom.

## Scenarios

> As a reviewer, I want Down to reach the context subsections instead of skipping the whole panel.

```gherkin
Given a context panel carrying System, Session, and Turn
When I press Alt+Down repeatedly from the Context root
Then the cursor visits System, Session, Turn, Rationale, and Action Plan in that order
```

> As a reviewer, I want the end of the tree to stop rather than wrap.

```gherkin
Given the cursor on the Action Plan root
When I press Alt+Down
Then the tree scrolls to its last visible row
And the cursor does not move to the Context root
```

> As a reviewer, I want the mirror behaviour at the top.

```gherkin
Given the cursor on the Context root
When I press Alt+Up
Then the tree scrolls to its first row
And the cursor does not move to the Action Plan root
```

## Edge Cases
- **No context panel**: If `project_context` is `None`, then the sequence is Rationale followed by Action Plan only, because the walk derives from the tree and never references an absent section.
- **No history**: If the session has no history entries, then no History leaf exists and the walk skips it, because the sequence is read from the built tree rather than from a constant.
- **Cursor on a child**: If the cursor sits on a file row inside Session, then Next advances to Turn, because the containing section is the last section node at or before the cursor in render order.
- **Single section**: If a plan carries neither context nor a recognized rationale, then Next and Prev both scroll, because there is nowhere to jump.
- **Collapsed destination**: If the target root is collapsed, then it is expanded before the cursor moves, because jumping into a collapsed node would hide the destination.
- **Right pane focused**: If focus is in the right pane, then the same keys keep their pane-local scroll meaning, because the app-level handler only runs while the tree holds focus.
- **Repeated presses at the boundary**: If Next is pressed again after the tree reached its end, then nothing changes, because scroll-to-end is idempotent.

## Key Unknowns
- None. The spec fixes the no-wrap rule, and the tree is the focused widget whenever these bindings fire, so the scroll target is settled: the tree scrolls, and the right pane keeps its own bindings.

## Impact
1. `[NEW]` `section_sequence(tree)` in `textual_plan_reviewer_helpers.py` — a pure depth-first walk returning every node whose payload is a section sentinel, in tree order and recorded once each, so the sequence reflects whichever sections actually exist and an empty scope group's `(None)` placeholder does not add a second stop.
2. `[NEW]` `containing_section(node)` in the same module — returns the section governing a node: the last section node at or before it in render order, because the context pane renders each scope header beside its rows rather than above them.
3. `[MIGRATE]` `ReviewerApp.action_jump_next` and `action_jump_prev` — replace the constant list and the modulo with the derived sequence, scrolling to the end or the start instead of wrapping.
4. `[MIGRATE]` `ActionTree` — expose a `jump_to_node(node)` that expands the target before moving the cursor.
5. `[PRUNE]` `ActionTree.jump_to_section` — remove the direct-children-only search once both actions use the derived sequence.
6. `[MIGRATE]` The reviewer component page's Keyboard bindings section — record the boundary behaviour and the subsection targets.

## Deliverables
- [x] **Harness** — Extend the TUI driver so a test can build a tree with a synthetic context panel, including the no-history and no-context shapes.
- [x] **Core** — Implement `section_sequence` and `containing_section` as pure helpers with unit tests over a fully populated tree, a history-less tree, and a context-less tree.
- [ ] **Wiring** — Rewire `action_jump_next` and `action_jump_prev` onto the derived sequence, scrolling to the tree's end or start at the boundaries, and prove the order end to end through the driver.
- [ ] **Refactor** — Replace `jump_to_section` with `jump_to_node` and delete the direct-children-only search once both actions no longer call it.
- [ ] **Cleanup** — Update the reviewer component page's binding table with the boundary rule and the new subsection targets.

## Implementation Notes

### Harness — observable TUI driver and canonical context shapes

**Files:** `tests/harness/drivers/tui_driver.py`, `tests/harness/setup/reviewer_context_scenarios.py`, `tests/suites/unit/test_tui_driver.py`, `tests/suites/unit/test_reviewer_context_scenarios_harness.py`.

**What changed:** `TuiDriver` injects `project_context` at construction and exposes `tree(pilot)` and `cursor_data(pilot)` observers plus an `interaction()` async context manager that mounts the app and yields a pilot whose tree holds focus. `run_interaction` now delegates to `interaction()`, so key-driven tests and observation-driven tests share one mount path. Before this, `run_interaction` returned only after `run_test()` closed and no test could read the cursor mid-run.

**Signature stability:** `project_context`, `action_dispatcher`, and the doubled ports were added as keyword-only parameters and `console_tooling` kept its fourth positional slot, so all five existing `TuiDriver` construction sites compiled unchanged and needed no migration.

**Path-derived shapes:** the context pane partitions items through `is_own_session_path` and `is_session_history_path`, so the three shapes (`populated`, `history_less`, `none`) are built from real session paths under a fixed `SESSION_ROOT`. The invariant tests assert each shape through the same predicate the panel consumes, so a shape cannot silently stop meaning what its name says.

**Spec-bound defaults:** the driver's `console_tooling` and `action_dispatcher` defaults come from `spec_mock` in `tests/harness/setup/mocking.py`, which builds a `POSIXPathMock(spec=<seam type>)` without a container. Staging the driver put its former bare `MagicMock()` defaults under the TID251 banned-API rule, so the migration landed here rather than later. The specs are `ConsoleToolingHelper` and `ActionDispatcher` — the two classes the reviewer actually calls (`find_editor`, `get_diff_viewer_command`, `dispatch_and_execute`) — so no construction site can reach an attribute the seam lacks. `register_mock` now delegates to the same factory, leaving one construction site for every harness double.

### Core — derivation helpers with positional section membership

**Files:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`, `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`, `tests/suites/unit/adapters/inbound/test_section_navigation.py`.

**What changed:** `SECTION_SENTINELS` derives the navigation set from the seven sentinel constants, so a new section cannot be introduced without joining the walk, and `is_section_payload` gates the membership test on `str` because a file row carries an unhashable `ContextItem` and the agent row carries a dict. `section_sequence(tree)` records every section payload in preorder, first occurrence only, and `containing_section(node)` returns the section governing a node.

**Corrected membership model:** the first implementation walked parent pointers and the tests rejected it — a Session file row resolved to `CONTEXT_ROOT`. `build_context_section` renders each scope header and its rows as siblings under the Context root (`add_leaf` for both), so ancestry cannot identify a row's group. Membership is positional: the last section node at or before the node in render order. That single rule resolves a section node to itself, a scope row to its header, and the invisible root to `None`, and it matches the flat panel the reviewer actually draws. The agent row therefore resolves to `SYSTEM_LABEL`, the group it renders under, which the corrected test pins.

**One traversal:** both helpers read the tree through a shared `_preorder`, so "render order" has one implementation rather than a duplicated walk. The `_logic` import stays function-local to preserve the existing import direction.

## Verification
1. **Subsection walk:**
   Run `uv run teddy start -m "plan a small refactor"` and press Alt+Down repeatedly from the Context root.
   Verify the cursor visits System, Session, Turn, Rationale, and Action Plan in order.
2. **Bottom boundary:**
   With the cursor on the Action Plan root, press Alt+Down.
   Verify the tree scrolls to its last row and the cursor stays on Action Plan.
3. **Top boundary:**
   Press Alt+Up on the Context root.
   Verify the tree scrolls to its first row and the cursor does not move.
