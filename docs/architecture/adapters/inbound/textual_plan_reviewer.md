# Component Design: TextualPlanReviewer
- **Status:** Refactoring
- **Classification:** Inbound Adapter
- **Source:** [`src/teddy_executor/adapters/inbound/textual_plan_reviewer.py`](/src/teddy_executor/adapters/inbound/textual_plan_reviewer.py)

## Purpose
Implements the `IPlanReviewer` inbound port with a dual-pane `Textual` TUI. It provides an interactive terminal experience for reviewing, modifying, and selectively executing a plan before it runs. Supporting logic lives in the sibling `textual_plan_reviewer_*.py` modules.

## Consumers
- [`ExecutionOrchestrator`](../../core/services/execution_orchestrator.md): Invokes review through the `IPlanReviewer` port for interactive plans.

## Dependencies
- [`ISystemEnvironment`](../../core/ports/outbound/system_environment.md): Launches the external editor for context-aware editing.
- **`is_cli_editor` / `normalize_editor_basename`** (`teddy_executor.core.utils.editor_names`): Classify editor commands by stripping Windows launcher suffixes and lowercasing the basename. The module-level `_is_cli_editor` in `textual_plan_reviewer_editor.py` stays a thin delegator because `textual_plan_reviewer_previews` imports it.
- [`WebContentService`](../../core/services/web_content_service.md): Serves a READ action's URL preview from the session cache, fetching once on a miss.
- [`IAgentCatalog`](../../core/ports/outbound/agent_catalog.md): Supplies the persona roster the System node's agent switch offers (slice 04-06). Injected at the composition root like `console_tooling`, so a reviewer test drives both the populated and the empty roster without touching `.teddy/prompts/`.

## Class Invariants
- `stdin_ownership`: While the app runs, the reviewer claims `stdin_owned()` so the session quit-key listener backs off and the TUI's own `q` binding stays authoritative.
- `rationale_heading_only`: Only a `### Section` heading starts a rationale node, and only `Summary`, `Expectation`, `Progress`, or `Notes` is accepted as a title. The tree splits on `\n(?=### )` and strips the `### ` marker; any other content, including a numeric `1. Section` marker, merges into the preceding node. A rationale with no recognized heading at all, such as one written before the section contract, renders as a single `Raw` node holding its entire content and styled quieter than the protocol sections, instead of rendering nothing.
- `log_is_read_only`: Viewing an action log bypasses the apply-changes confirmation prompt.
- `session_root_grouped_context`: The context pane groups reads by the DTO's `session_root`. Only paths under that root become History; a foreign session's read keeps the scope group it arrived in, because the exclusion uses `is_own_session_path` rather than the coarse "under `sessions/`" test, and its label falls back to the raw path. A `None` root keeps the legacy grouping.
- `mutable_plan_models`: The `Plan` and `ActionData` models are unfrozen so the reviewer can update them in memory.
- `cache_served_url_preview`: A READ preview on an `http`/`https` resource resolves through `WebContentService.fetch_one` with `project_context.session_root`, so previewing a URL a READ already fetched costs no network round trip, and a preview miss is stored for the following turn. A missing project context reads as no session, so the preview falls back to an uncached fetch.
- `context_node_e_dispatch`: `e` resolves by node kind and is never silently dead on a context node. A `ContextItem` opens its own path; the Session and Turn roots open their `.context` manifest through `launch_editor` with `skip_confirm`, so the manifest is read-only in place and no temp file is harvested; the System node opens the injected roster. The Turn manifest is `turn.context` beside `plan.plan_path` and the Session manifest is `session.context` under `project_context.session_root`, so neither directory is guessed. A `--plan-content` run has no `plan.plan_path`, so its Turn node notifies that the turn context is unavailable, and a missing manifest notifies with its path rather than opening an empty buffer. Enter and Space still toggle selection, because `e` must not absorb the toggle binding.
- `cost_rows_share_one_format`: The Context root's Model, Provider, and Session Cost rows read from the DTO rather than from ambient configuration, and the cost row routes through `format_cost_usd`, so the panel cannot disagree with the terminal telemetry line or the guardrail notice about the same session. Unrecorded cost renders `$???` while recorded zero renders `$0.0000`, because those are different facts about a run, and every recorded amount renders at exactly four decimal places.
- `single_panel_inset`: One gutter governs the left pane, both right-pane variants, and every row. `PANEL_INSET` is declared once, on the two pane containers only (`#left-pane` and `#right-pane`), and `build_tui_css` renders it into the stylesheet through a sentinel substitution, because this stylesheet defeats `str.format`, `%`, and `string.Template` (literal `{}` blocks, `65%` widths, and Textual `$variables`). No child declares its own padding — `#rationale-content`, `ListItem`, and `Tree` carry none — because CSS padding stacks and a second declaration would put that row back on a different gutter. `#right-pane` keeps its `border-left`, which the padding sits inside.

## Inbound Ports
- **`IPlanReviewer`**: Exposes `review(plan, project_context=None)` and `review_action(action, total_actions, agent_name=None)`.

## Outbound Ports
- **`ISystemEnvironment`**: Consumed to open the editor for parameter edits.
- **`WebContentService`**: Consumed to produce a READ preview's URL body without a redundant fetch.

## Data Contracts
- **`Plan`** and **`ActionData`** (`teddy_executor.core.domain.models.plan`): The reviewed objects, updated in memory.
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): Optional context metadata shown in the context pane.

## Operations

### `review(plan, project_context=None) -> Optional[Plan]`
- **Preconditions:** `plan` is a valid `Plan`.
- **Postconditions:** Returns the plan carrying the user's selections and edits, or `None` when the user cancels. The dual-pane layout shows a 65% action tree and a 35% parameter detail pane, both carrying the single `PANEL_INSET` gutter so rationale prose, context rows, parameter rows, and the action tree all start at the same column. Selecting the Context root shows an aggregate token breakdown: the `System` line sums the system-prompt and system-info tokens, and the `Total Context` line divides content plus system-prompt tokens by the model window. The History group lists only this session's own turns, and the Session/Turn/History token split applies the same root gate.

### `review_action(action, total_actions, agent_name=None) -> tuple[bool, str]`
- **Postconditions:** Returns `(should_execute, captured_message)` for sequential review.

### Keyboard bindings
`s` submits the plan; `a` toggles all actions; `e` edits the highlighted node — an action (external editor for CREATE and EDIT, modal for EXECUTE and RESEARCH) or a context node (a file path, the Session root, the Turn root, or the System node's agent roster); `d` opens the read-only action log; `r` reverts manual modifications; `v` views the original plan file; `x` marks a step executed; `m` adds or edits a user message; `q` cancels and exits.

### Action log format
The reviewer renders an action log as a structured Markdown document: an `### {ACTION_TYPE}: {SUMMARY}` header, a `- **Status:** {STATUS}` line, and quadruple-backtick fences around `stdout`, `stderr`, and `diff`.
