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
- [`Model Identity`](../../core/utils/model_identity.md): Supplies `split_model_identity`, which derives the displayed Provider from the DTO's `model_name` at render time, so the panel stores no second copy of a value it can compute.
- [`Money`](../../core/utils/money.md): Supplies `format_cost_usd`, which renders the Session Cost row, so the panel shares one money standard with the terminal telemetry line and the guardrail notice.

## Class Invariants
- `stdin_ownership`: While the app runs, the reviewer claims `stdin_owned()` so the session quit-key listener backs off and the TUI's own `q` binding stays authoritative.
- `bracket_live_during_review`: The reviewer mounts inside `ExecutionOrchestrator.execute`, which both interruptible boundaries run inside the shared `interrupt_scope`, so the SIGINT disposition and the quit-key listener are already live while the TUI is up. The `stdin_owned()` claim is what keeps the raw reader off Textual's keys, so `q` stays the TUI's binding during review and a stateless `execute` run presents the same key semantics as a session.
- `rationale_heading_only`: Only a `### ` heading starting at column zero starts a rationale node, and every such heading does so whatever its title, in the authored order, so a plan that renames, adds, or reorders a section stays reviewable instead of being folded into the one before it. `#### ` and an indented `### ` line stay body text, and only the blank lines around a body are trimmed, so an indented first line survives verbatim and an empty section keeps its node with an empty body. A heading inside a fenced block stays body text: a fence opens on three or more backticks or tildes (at most three leading spaces) and closes only on the same character at or above the opening length, and an unclosed fence keeps the rest of the rationale inside its section rather than tearing the block in two. Text before the first heading becomes a leading `Untitled` node, and a rationale carrying no heading at all renders as one `Untitled` node holding its whole content, because a heading-less rationale is an untitled section rather than machine output. The quieter `[#888888 italic]` styling keys on the title string equalling `Untitled`, so an author who genuinely writes `### Untitled` gets the same quieter label — a deliberate trade-off, since keying on position instead would mis-style a preamble node carrying a heading elsewhere.
- `log_is_read_only`: Viewing an action log bypasses the apply-changes confirmation prompt.
- `session_root_grouped_context`: The context pane groups reads by the DTO's `session_root`. Only paths under that root become History; a foreign session's read keeps the scope group it arrived in, because the exclusion uses `is_own_session_path` rather than the coarse "under `sessions/`" test, and its label falls back to the raw path. A `None` root keeps the legacy grouping.
- `mutable_plan_models`: The `Plan` and `ActionData` models are unfrozen so the reviewer can update them in memory.
- `cache_served_url_preview`: A READ preview on an `http`/`https` resource resolves through `WebContentService.fetch_one` with `project_context.session_root`, so previewing a URL a READ already fetched costs no network round trip, and a preview miss is stored for the following turn. A missing project context reads as no session, so the preview falls back to an uncached fetch.
- `context_node_e_dispatch`: `e` resolves by node kind and is never silently dead on a context node. A `ContextItem` opens its own path; the Session and Turn roots open their `.context` manifest through `launch_editor` with `skip_confirm`, so the manifest is read-only in place and no temp file is harvested; the System node opens the injected roster. The Turn manifest is `turn.context` beside `plan.plan_path` and the Session manifest is `session.context` under `project_context.session_root`, so neither directory is guessed. A `--plan-content` run has no `plan.plan_path`, so its Turn node notifies that the turn context is unavailable, and a missing manifest notifies with its path rather than opening an empty buffer. Enter and Space still toggle selection, because `e` must not absorb the toggle binding.
- `cost_rows_share_one_format`: The Context root's Model, Provider, and Session Cost rows read from the DTO rather than from ambient configuration, and the cost row routes through `format_cost_usd`, so the panel cannot disagree with the terminal telemetry line or the guardrail notice about the same session. Unrecorded cost renders `$???` while recorded zero renders `$0.0000`, because those are different facts about a run, and every recorded amount renders at exactly four decimal places.
- `single_panel_inset`: One gutter governs the left pane, both right-pane variants, and every row. `PANEL_INSET` is declared once, on the two pane containers only (`#left-pane` and `#right-pane`), and `build_tui_css` renders it into the stylesheet through a sentinel substitution, because this stylesheet defeats `str.format`, `%`, and `string.Template` (literal `{}` blocks, `65%` widths, and Textual `$variables`). No child declares its own padding — `#rationale-content`, `ListItem`, and `Tree` carry none — because CSS padding stacks and a second declaration would put that row back on a different gutter. `#right-pane` keeps its `border-left`, which the padding sits inside.
- `tree_derived_section_walk`: The jump sequence is read from the tree rather than from a fixed list, so it holds exactly the sections the panel built — a plan without context has no Context stop and a session without history no History stop — and both ends terminate by scrolling instead of wrapping, because a wrap would teleport the reviewer from the end of the plan back to the top of the panel.

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
- **Postconditions:** Returns the plan carrying the user's selections and edits, or `None` when the user cancels. The dual-pane layout shows a 65% action tree and a 35% parameter detail pane, both carrying the single `PANEL_INSET` gutter so rationale prose, context rows, parameter rows, and the action tree all start at the same column. Selecting the Context root shows an aggregate token breakdown: the `System` line sums the system-prompt and system-info tokens, and the `Total Context` line divides content plus system-prompt tokens by the model window. The History group lists only this session's own turns, and the Session/Turn/History token split applies the same root gate. Beneath the token breakdown the same aggregate view appends unbulleted `Model` and `Provider` rows from the DTO's `model_name` and a `Session Cost` row from its `session_cost`, so a reviewer sees which model will answer and what the session has spent before approving; the `• ` prefix stays reserved for the token breakdown's sub-rows.

### `review_action(action, total_actions, agent_name=None) -> tuple[bool, str]`
- **Postconditions:** Returns `(should_execute, captured_message)` for sequential review.

### Keyboard bindings
`s` submits the plan; `a` toggles all actions; `e` edits the highlighted node — an action (external editor for CREATE and EDIT, modal for EXECUTE and RESEARCH) or a context node (a file path, the Session root, the Turn root, or the System node's agent roster); `d` opens the read-only action log; `r` reverts manual modifications; `v` views the original plan file; `x` marks a step executed; `m` adds or edits a user message; `q` cancels and exits.

`q` behaves identically in a session and a stateless `execute` run, because both enter the shared interrupt bracket before the reviewer mounts: it cancels the review, and once execution has begun the same key drains the plan into an `INTERRUPTED` report instead of escaping as a traceback.

`alt+down`, `ctrl+down`, and `shift+down` advance to the next section; `alt+up`, `ctrl+up`, and `shift+up` step back to the section governing the cursor or to the previous one. The walk is read from the tree, so every section the panel actually built is a stop — the Context root's System, Session, Turn, and History groups included — and a plan without context or a session without history simply has fewer stops. A destination inside a collapsed group is expanded before the cursor lands. The walk does not wrap: past the last section the tree scrolls to its last row, and before the first it scrolls to its first row, so a boundary press never teleports the cursor from the end of the plan back to the top of the panel. Prev returns to the section governing a child row first, so one press never skips past the cursor's own group. The right pane keeps these keys for its own meaning: `RationaleDetail` and `ParameterDetail` bind them to scroll-to-top and scroll-to-bottom, and the jump actions only run while `ActionTree` holds focus.

### Parameter editing
Selecting a parameter row in the right pane resolves in exactly one of three arms, and every arm writes back through the same `_apply_param_edit`:

| Selected value | Arm | Why |
| --- | --- | --- |
| The `path` key | `PathInputScreen` | A path is a single token, so the file-picker semantics stay unchanged. |
| A rendered value `needs_external_editor` accepts | `launch_editor` | Any newline, or a length strictly above `MAX_INLINE_PARAM_LENGTH` (100 characters). |
| Anything else | `ParameterEditModal` | A single-line `Input` is honest for a short, single-line value. |

The test runs on the rendered string, so a joined list is judged after `", "` — the same separator `_apply_param_edit` re-splits on — and a value of exactly 100 characters still stays inline. A dismissed editor returns `None` and leaves the parameter untouched, while an emptied buffer returns an empty string and clears it, so the arm distinguishes `None` from `""` instead of testing truthiness. The editor result loses exactly one appended newline, and only when the original value did not already end with one, so an editor round trip of an already terminated command is not recorded as a modification; a Windows CRLF pair counts as one newline and is removed as a pair. `e` on an action node keeps its own split — the editor for CREATE and EDIT bodies, the modal for EXECUTE and RESEARCH command and queries — because that path never goes through this branch.

### Action log format
The reviewer renders an action log as a structured Markdown document: an `### {ACTION_TYPE}: {SUMMARY}` header, a `- **Status:** {STATUS}` line, and quadruple-backtick fences around `stdout`, `stderr`, and `diff`.
