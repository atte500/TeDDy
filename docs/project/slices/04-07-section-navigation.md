# Slice: Boundary-Aware Section Navigation
- **Status:** Completed
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
4. `[MIGRATE]` `ActionTree` — expose a `jump_to_node(node)` that expands the target and its ancestors before moving the cursor, so a subsection under a collapsed root is reachable, and defer the move until a newly revealed node has a line, because `move_cursor` records the target's line verbatim and `-1` moves nowhere.
5. `[PRUNE]` `ActionTree.jump_to_section` — remove the direct-children-only search once both actions use the derived sequence.
6. `[MIGRATE]` The reviewer component page's Keyboard bindings section — record the boundary behaviour and the subsection targets.

## Deliverables
- [x] **Harness** — Extend the TUI driver so a test can build a tree with a synthetic context panel, including the no-history and no-context shapes.
- [x] **Core** — Implement `section_sequence` and `containing_section` as pure helpers with unit tests over a fully populated tree, a history-less tree, and a context-less tree.
- [x] **Wiring** — Rewire `action_jump_next` and `action_jump_prev` onto the derived sequence, scrolling to the tree's end or start at the boundaries, and prove the order end to end through the driver.
- [x] **Refactor** — Delete `jump_to_section`, now that both actions reach the tree through `jump_to_node`, and port its two unit tests onto the new method.
- [x] **Cleanup** — Update the reviewer component page's binding table with the boundary rule and the new subsection targets.
- [x] **Harness** — Add `TuiDriver.find_node` as the single tree-node lookup, cover it in the driver's contract test, and replace the two duplicated traversals in the navigation test modules.

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

### Wiring — derived walk with a deferred jump

**Files:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`, `src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py`, `tests/suites/acceptance/test_tui_section_boundaries.py`.

**What changed:** both jump actions read `section_sequence(tree)`, resolve the cursor's governing section through `containing_section`, and translate it with a module-level `_section_index`. The arithmetic carries the no-wrap rule: `index + 1 < len(sections)` jumps and the else branch scrolls, so an ungoverned cursor at the invisible root (`index == -1`) lands on the first section and an exhausted sequence scrolls to the last row without moving the cursor. Prev returns to the governing section first when the cursor sits on a child, then steps back, and scrolls home at index 0. `ActionTree.jump_to_node` expands the whole lineage before moving the cursor.

**Deferred move (why the first press was lost):** `spikes/debug/section-jump-expand/probe.py` showed a child's `line` still `-1` immediately after its parent's `expand()`, while `Tree.move_cursor` assigns `cursor_line = node._line` — so the first move onto a just-revealed node recorded `-1` and went nowhere. Exactly one press was swallowed, always the first, which is why the file-row case passed: it expands the Context root itself before pressing. `probe_fix.py` then compared the remedies: `call_after_refresh(move_cursor)` lands inside a single `pilot.pause()`, whereas `refresh(layout=True)` computes the line but never re-applies the move that already ran against `-1`. `jump_to_node` therefore defers only when `node.line < 0`, so already-visible targets keep their synchronous move and existing pause-free callers stay unaffected.

**Payload-identity fallback:** `_section_index` matches by identity first and by payload second, because `containing_section` can return an empty-scope `(None)` placeholder leaf that `section_sequence` dropped in favour of its header. Payloads are unique within a sequence, so the fallback cannot be ambiguous.

**Acceptance observability:** the new module drives the app through `TuiDriver`, whose doubles are spec-bound, instead of the older acceptance file whose bare `MagicMock` would trip the banned-API rule when staged. The boundary assertions read `scroll_y` against `max_scroll_y` and `0` on a 40-action plan, with the overflow itself asserted as a precondition so a non-scrolling viewport fails loudly rather than passing vacuously; the top-boundary case scrolls away first, because the Context root is the first row and a naive `scroll_y == 0` would hold trivially.

### Refactor — deleting the superseded jump

**Files:** `src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py`, `tests/suites/unit/adapters/inbound/test_section_navigation.py`, `tests/suites/unit/adapters/inbound/test_reviewer_app_context_previews.py`, `tests/harness/setup/reviewer_context_scenarios.py`, `tests/suites/unit/test_tui_driver.py`, `tests/suites/acceptance/test_tui_section_boundaries.py`.

**What changed:** `ActionTree.jump_to_section` is gone, together with the direct-children-only search that made a context subsection unreachable in the first place. Its two unit tests moved onto `jump_to_node`: the first still proves a jump moves the cursor between visible sections (the immediate branch), and the second covers the collapsed-subsection case (the deferred branch). The previews case now resolves the Context root node instead of passing a section key, because `jump_to_node` takes a node. The deleted method has no surviving reference in `src/` or `tests/`, and the suite count is unchanged because one case replaced another rather than being added or dropped.

**Why the port is not a rename:** `jump_to_section` scanned the invisible root's children for a section id, so "no such section" was a genuine branch that deserved a test. A node parameter cannot be mistaken for a missing key, and `jump_to_node(None)` fails on `node.line` rather than no-opping, so that premise dissolved instead of moving. What replaced it is the branch the node parameter actually introduced — a collapsed group expanded before the cursor lands — which until now had no direct unit coverage and was proven only indirectly by the boundary acceptance module and the probes.

**Single-sourced plan builder:** the `### Summary` plan every navigation scenario drives now lives as `reviewer_plan(action_count=1)` beside the canonical panel shapes in `reviewer_context_scenarios.py`, replacing three verbatim copies across the unit, acceptance, and driver test modules. The `action_count` parameter is what lets a boundary scenario overflow the tree viewport. The per-file `_driver` helpers stay: they are fixture wiring over `mock_env`/`mock_fs`, not duplicated content.

**Deliberately deferred:** collapsing `ActionTree.CONTEXT_ROOT`/`RATIONALE_ROOT`/`ACTION_PLAN_ROOT` into the constants `_logic.py` already owns would require staging `test_tui_section_navigation.py`, which still builds bare `MagicMock`, so the collapse is recorded as a milestone item rather than smuggled into this commit.

### Cleanup — reviewer page and harness registration

**Files:** `docs/architecture/adapters/inbound/textual_plan_reviewer.md`, `docs/architecture/ARCHITECTURE.md`, `docs/project/milestones/06-cross-cutting-consolidation.md`, `docs/architecture/tests/drivers/tui_driver.md` (new), `docs/architecture/tests/setup/reviewer_context_scenarios.md` (new).

**Reviewer page:** the Keyboard bindings section now names all eight jump keys — `alt`, `ctrl`, and `shift` in both directions — and states that the walk is read from the tree, so the Context root's System, Session, Turn, and History groups are stops rather than a single opaque panel. It records the collapsed-destination expansion, the governing-section return on Prev so one press never skips the cursor's own group, and the right pane's pane-local scroll meaning. A `tree_derived_section_walk` invariant pins the two properties that would otherwise erode silently: the sequence holds exactly the sections the panel built, and both ends terminate by scrolling instead of wrapping.

**Harness registration:** `TuiDriver` and `ReviewerContextScenarios` had design-worthy structure but no Component Map row and no page, so both were authored from the component-design template (`Status: Implemented`, `Classification: Test Driver` / `Test Setup`) and linked from the Test Harness table. The driver page records why the Harness commit cleared TID251 — an omitted `console_tooling` or `action_dispatcher` arrives through `spec_mock`, so it cannot answer an attribute the real seam lacks — and why every cursor, focus, or scroll assertion must run inside `interaction()`, because the app is unmounted on exit. The scenarios page records `paths_decide_the_shape` and states plainly that `reviewer_plan` enforces no precondition on `action_count`, since no guard exists and the plan is only ever built from literal test constants.

**Deferred literal recorded, not smuggled:** the slice claimed the `ActionTree` root-constant collapse was "recorded as a milestone item" while milestone 06 did not carry it. Its Requirement 1 now names the three duplicated section ids together with the hard prerequisite — `test_tui_section_navigation.py` still builds bare `MagicMock`, so it must migrate onto spec-bound doubles before the collapse can be staged.

**Status left as `Refactoring`:** the reviewer page keeps that status deliberately. This slice scoped only its bindings and invariant sections, and milestone 04 carries five further reviewer slices that keep editing the same surface, so flipping it to `Implemented` would overstate what is finished.

**Stale references:** the sweep over `src/`, `tests/`, `docs/`, `spikes/`, and `scripts/` — wider than the earlier `NO_REFS` probe, which by construction skipped `docs/` and `spikes/` — finds `jump_to_section` only in this document's own history.

### Harness — the shared tree lookup

**Files:** `tests/harness/drivers/tui_driver.py`, `tests/suites/unit/test_tui_driver.py`, `tests/suites/acceptance/test_tui_section_boundaries.py`, `tests/suites/unit/adapters/inbound/test_section_navigation.py`.

**What changed:** the slice's two navigation modules each carried the same preorder scan under a different name — `_find_node` in the boundary module and `_first_node` in the unit module, identical apart from its message. `TuiDriver.find_node(pilot, matches)` now performs that walk once, returns the first node in render order whose payload satisfies the predicate, and raises an assertion naming the failed search when nothing matches. Three call sites migrated onto it and both private helpers were deleted.

**Why it is a Harness deliverable:** it adds a public observation port to a first-class test boundary, which the architecture contract expects to carry its own contract tests. The Red step observed both new tests failing with `AttributeError: 'TuiDriver' object has no attribute 'find_node'`, so neither passed for an incidental reason; the targeted run then reported `20 passed` across the four affected modules, and the unfiltered suite rose by exactly the two new cases.

**Appended after Cleanup, deliberately:** the deliverable order in this slice was written before implementation, and only the Verification phase's test-hygiene audit surfaced the duplication — the two modules were created by earlier deliverables and their builders were single-sourced by the Refactor, so the traversal itself went unnoticed until the audit looked for it. The list records the extraction as the tail deliverable rather than pretending it was planned.

**Predicates stay local:** each module still passes its own one-line predicate (`_is_session_file_row`, `_is_agent_row`, and one inline `getattr` check), because a predicate states which row its scenario wants rather than re-implementing shared infrastructure. The per-file `_driver` helpers likewise stay: they wire `mock_env`/`mock_fs`, they do not duplicate content.

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
