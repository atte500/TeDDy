# Slice: Context-Aware `e` Actions in the Reviewer
- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** [04-05-context-metadata](./04-05-context-metadata.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md), [IAgentCatalog](/docs/architecture/core/ports/outbound/agent_catalog.md), [LocalAgentCatalog](/docs/architecture/adapters/outbound/local_agent_catalog.md), [ISessionManager](/docs/architecture/core/ports/outbound/session_manager.md)
- **Scope Slug:** `context-actions`

## Goal
Make `e` do the obvious thing on every context node — open the session or turn manifest, open the file itself, or switch persona — so the key stops being silently dead on the panel a reviewer consults most, and so a persona switch re-composes the agent+MRP system prompt from there on exactly as `resume -a` does.

## Context
- `check_action_logic` (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`): Returns `False` for any node whose payload is neither `ActionData` nor `ContextItem`, which covers `CONTEXT_ROOT`, `SYSTEM_LABEL`, `SESSION_LABEL`, `TURN_LABEL`, and `HISTORY_LABEL`; for a `ContextItem` it allows only `toggle_selection` and navigation. `edit_details` is therefore disabled on every context node today.
- `ReviewerApp.action_edit_details`: Branches three ways — redirect to `view_details` for an executed action, delegate to the list-view editor when the right pane holds focus, and otherwise call `edit_action_logic`.
- `launch_editor(app, content, suffix=..., persistent_path=..., skip_confirm=True)` (`textual_plan_reviewer_editor.py`): Opens a real file in place and cleans up only temp files, which is exactly the seam `preview_readonly` already uses to show a READ resource without harvesting edits.
- `app.plan.plan_path`: Names the on-disk `plan.md`; its parent directory is the current turn directory that owns `turn.context`. `app.project_context.session_root` names the session directory that owns `session.context`.
- Personas: `PromptManager` resolves a persona only from `.teddy/prompts/`, which `teddy init prompts` populates by copying the six bundled prompt files; there is no bundled fallback at resolution time. `list_prompt_names()` in `src/teddy_executor/prompts.py` already scans that directory for stems, so the roster adapter delegates to it rather than reimplementing discovery. A workspace may therefore legitimately carry a reduced, extended, or empty roster.
- `canonical_agent_name` (`src/teddy_executor/core/utils/string.py`): Already normalizes persona names case-insensitively, so the roster and the selection must present canonical names.
- **Switch semantics (product decision, 2026-11-26):** picking a persona on the System node behaves like `resume -a` — the agent plus MRP system prompt is re-composed from that point on. `PromptManager.compose_system_prompt(agent_name)` (`prompt_manager.py:206`) is that composition and `fetch_system_prompt(agent_name, turn_path)` (`:157-171`) is what the planner calls, so the switch changes the name the next turn is planned with rather than editing a prompt file or a config value. The current turn keeps its already-composed plan, which is why the effect is visible from the next turn's header and trace.
- **Session-root prompts win:** `fetch_system_prompt` returns an existing `<session>/<agent>.md` verbatim and never re-composes it, so a customized session prompt keeps governing that persona even after a switch. That is correct — the customization is deliberate — but the slice must state it, because it is the one case where a newly selected persona's workspace prompt does not take effect.
- **Persistence:** `ISessionManager.set_session_agent(session_name, agent_name)` (`session_service.py:559`) already writes `meta["agent_name"]`, the same field `resume -a` sets and `_echo_config_success` reads (`session_cli_handlers.py:1524`), so the switch writes that field instead of adding a second one.
- **Model row coupling:** the effective model resolves flag, then `agents.<persona>.model`, then `llm.model`, so after a switch the Model row added by [04-05](./04-05-context-metadata.md) must be re-resolved through the overlay; otherwise the panel keeps naming the previous persona's model while a different one answers. That coupling is why this slice lands after 04-05 rather than beside it.
- `docs/project/specs/interactive-session-workflow.md`, Context Node Interactions: Fixes the first two behaviours — `e` on the Session or Turn root opens the corresponding `.context` file, and `e` on a file path node opens that file.

## Scenarios

> As a reviewer, I want to read the session manifest without leaving the TUI.

```gherkin
Given a context panel whose session root is .teddy/sessions/20260124-add-user-auth
When I press e on the Session label
Then .teddy/sessions/20260124-add-user-auth/session.context opens in my editor
```

> As a reviewer, I want to inspect a context file the plan will read.

```gherkin
Given a context panel listing docs/project/PROJECT.md
When I press e on that file row
Then docs/project/PROJECT.md opens in my editor
And no confirm prompt is shown
```

> As a reviewer, I want to switch persona from the panel and have it take effect.

```gherkin
Given a context panel whose System node shows Pathfinder
When I press e on the System node and select Developer
Then the session records Developer as its agent
And the next turn is planned with the Developer persona and the shared protocol re-composed
And the Model row shows the model resolved for Developer rather than for Pathfinder
```

## Edge Cases
- **Missing manifest**: If the session root is set but `session.context` is absent, then the app notifies instead of opening an empty buffer, because a blank editor would misrepresent a missing file.
- **Unknown turn directory**: If `plan.plan_path` is `None` (a `--plan-content` run), then the Turn label notifies that the turn context is unavailable, because the reviewer must not guess a directory.
- **Pruned file**: If a `ContextItem` points at a path that no longer exists, then the app notifies with the path, because a context entry can outlive the file it names.
- **Toggle preserved**: If the user presses Enter or Space on a context item, then selection still toggles, because `e` must not absorb the toggle binding.
- **No session in scope**: If `project_context.session_root` is `None`, then the System node notifies that no session is in scope and the panel stays unchanged, because a persona switch persists into a session and must not invent one.
- **Missing handles**: If the app holds no agent catalog or no session manager, then the System node notifies that switching is unavailable instead of raising, because `ReviewerApp` is constructed across roughly twenty-five call sites and an absent optional handle must not crash the reviewer.
- **Empty roster**: If `.teddy/prompts/` holds no prompt file, then the modal is not opened and the app notifies that no personas are installed, because prompt resolution reads only `.teddy/prompts/` and never falls back to the bundled resources — offering a name the planner cannot load would be a false promise.
- **Dismissed switch**: If the agent modal is dismissed, then nothing changes and no metadata is written, because an abandoned selection must be inert.
- **Current persona marked**: If the roster opens, then the active persona is marked as current, because a menu that hides the present choice invites accidental re-selection.
- **Session-root prompt**: If the newly selected persona has a stored `<session>/<persona>.md`, then that stored prompt governs and only the header and Model row change, because `fetch_system_prompt` never re-composes a session prompt.
- **Model overlay absent**: If `agents.<persona>.model` is unset for the new persona, then the Model row falls back to `llm.model`, because the overlay merge leaves omitted keys on the global default.

## Key Unknowns
- None. The switch semantics are settled by the 2026-11-26 product decision, the roster seam (`list_prompt_names`) and the persistence primitive (`set_session_agent`) both already exist, and every branch above is drivable through the injected catalog fake.

## Impact
1. `[NEW]` `IAgentCatalog` outbound port (`src/teddy_executor/core/ports/outbound/agent_catalog.py`) with `list_agents() -> tuple[str, ...]` returning canonical names in a stable order.
2. `[NEW]` `LocalAgentCatalog` adapter (`src/teddy_executor/adapters/outbound/local_agent_catalog.py`) delegating to `list_prompt_names()`, canonicalizing each stem, and translating a listing failure into `AgentCatalogError`.
3. `[NEW]` `AgentSelectScreen` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_widgets.py`, a `ModalScreen[str]` following the `PathInputScreen` shape.
4. `[MIGRATE]` `check_action_logic` — allow `edit_details` on `ContextItem` and on every context sentinel, keeping the executed-action gates unchanged.
5. `[MIGRATE]` A new context-node handler beside `preview_readonly` in `textual_plan_reviewer_previews.py`, resolving the node kind to a file path or the roster modal.
6. `[MIGRATE]` `ReviewerApp.__init__`, `TextualPlanReviewer`, and the reviewer registry — inject the catalog and the session manager as optional keyword handles defaulting to `None`, because the app is constructed at roughly twenty-five call sites across the suite and an optional handle keeps every one of them unbroken.
7. `[MIGRATE]` The System-node switch — persist the selection through `ISessionManager.set_session_agent` so the next turn's `fetch_system_prompt` composes the new agent+MRP pair, exactly as `resume -a` does.
8. `[MIGRATE]` The reviewer's Model and Provider rows from [04-05](./04-05-context-metadata.md) — re-resolve through the effective-model overlay after a switch.
9. `[MIGRATE]` The reviewer and CLI component pages — document the node-kind branches, the injected catalog, and the switch's re-composition semantics.

## Deliverables
- [ ] **Interface** — Define `IAgentCatalog` as a runtime-checkable protocol whose `list_agents()` returns canonical, de-duplicated names in a stable order, and add `AgentCatalogError` beneath `TeddyError`.
- [ ] **Harness** — Add an in-memory `FakeAgentCatalog` and register it in `TestEnvironment`, so reviewer tests drive both the populated and the empty roster without touching `.teddy/prompts/`.
- [ ] **Wiring** — Enable `edit_details` on context nodes and dispatch it to a handler that opens `session.context`, `turn.context`, or the selected file in place, completing the tracer bullet for the two spec-fixed behaviours.
- [ ] **Wiring** — Add `AgentSelectScreen` and route the System node to it, marking the current persona and notifying instead of opening the modal when the roster is empty, no session is in scope, or the handles are absent.
- [ ] **Adapter** — Implement `LocalAgentCatalog` over `list_prompt_names()`, canonicalizing each stem and translating a listing failure into `AgentCatalogError`.
- [ ] **Migration** — Persist the selection through `set_session_agent`, re-resolve the Model row after a switch, and prove the next generated plan names the new persona.
- [ ] **Cleanup** — Update the reviewer and CLI component pages, register `IAgentCatalog` and `LocalAgentCatalog` in the Component Map, and consolidate the duplicated context sentinels onto `logic.py`.

## Implementation Notes
- **Orientation audit:** every claim in `Context` was verified against source. `action_edit_details` branches three ways, `check_action_logic` allow-lists a `ContextItem` to toggle and navigation only, the context tree attaches the five sentinels plus a `{"type": "SYSTEM_PROMPT"}` leaf for the persona row, and `test_reviewer_app_context_previews.py` asserts aggregate rendering rather than `e`, so no part of this slice is pre-delivered.
- **Port shape:** outbound ports are `@runtime_checkable` Protocols with `...` bodies and docstring contracts, so the interface test asserts the attribute, the signature, and `isinstance` against the protocol instead of expecting an instantiation failure.
- **Optional handles:** `ReviewerApp(` is constructed at roughly twenty-five sites (the wrapper, `TuiDriver`, and unit and acceptance tests), so the catalog and the session manager arrive as keyword arguments defaulting to `None`; the System node notifies rather than raising when either is absent.
- **Re-partition:** the original Adapter deliverable bundled two unrelated changes — the roster adapter and the selection modal — so the modal became its own Wiring deliverable drawn against the harness fake, and the real adapter followed with its own integration test.
- **Model re-resolution:** `resolve_effective_model` (`core/domain/models/config_schema.py`) is the reuse seam; the reviewer re-runs it for the newly selected persona rather than recomputing the flag/persona/global overlay.
- **Session identity:** `project_context.session_root` is `.teddy/sessions/<name>`, absolute when derived from a turn directory, so `Path(session_root).name` is the session name `set_session_agent` receives.
- **Persistence is the whole switch:** `set_session_agent` writes `meta["agent_name"]`, recomposes the agent+MRP prompt through `fetch_system_prompt`, and prunes the previous persona's session-root file, so the reviewer adds no composition logic of its own.
- **Read-only opens:** `launch_editor(..., persistent_path=<real file>, skip_confirm=True)` opens a file in place without harvesting, which is the seam both the manifest rows and the file rows use.

## Verification
1. **Session manifest:**
   Run `uv run teddy start -m "plan a small refactor"`, highlight the Session label, and press `e`.
   Verify `session.context` opens read-only in your editor with no confirm prompt.
2. **Context file:**
   Highlight a file row under Turn and press `e`.
   Verify that file opens in place.
3. **Agent switch:**
   Highlight the System node and press `e`, then confirm a different persona.
   Verify the System node and Model row both update, and that the next plan's header names the new persona.
4. **Toggle intact:**
   Press Enter on a context file row.
   Verify the row still toggles between selected and deselected.
5. **Empty roster:**
   Move `.teddy/prompts` aside, press `e` on the System node, then restore the directory.
   Verify the app notifies that no personas are installed and opens no modal.
