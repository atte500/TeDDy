# Component: SessionOrchestrator
- **Status:** Implemented

## 1. Purpose / Responsibility

The `SessionOrchestrator` is a decorator-style service that wraps the stateless `ExecutionOrchestrator` to provide stateful session behavior. It is responsible for passing the session's cache directory to `ContextService.get_context()` to enable web content caching. It implements the `IRunPlanUseCase` but adds side-effects required for the interactive session workflow, such as persisting the execution report and triggering turn transitions.

**Tee Installation Guard:** The orchestrator cooperates with `SessionLifecycleManager` for history.log capture. The lifecycle manager installs the Tee *before* triggering planning to capture turn headers and metadata. The orchestrator's `execute()` method checks `lifecycle_manager.tee_active` before installing its own Tee, skipping if already active. This prevents double installation and ensures planning output is captured.

## 2. Ports

-   **Implements Inbound Port:** `IRunPlanUseCase`
-   **Uses Outbound Ports:**
    -   `ExecutionOrchestrator`: (Internal dependency) For core execution logic.
    -   `ISessionManager` (SessionService): For triggering turn transitions.
    -   `IFileSystemManager`: For persisting the formatted report.
    -   `IMarkdownReportFormatter`: For formatting the `ExecutionReport` before saving.

## 3. Implementation Details / Logic

1.  **Stateless Execution:** Delegated to the wrapped `ExecutionOrchestrator`.
2.  **Session Mode Detection:** If a `plan_path` is provided, the orchestrator enters "Session Mode".
### 3. Cache Directory Derivation: Before calling `ContextService`, the orchestrator derives the session's web content cache directory from `plan_path`:
    - `plan_path` = full path to the turn's `plan.md` (e.g., `.../mysession/01/plan.md`)
    - `cache_dir` = `str(Path(plan_path).parent.parent)` -> `.../mysession` (session root)
    - The cache file lives at `<session_root>/.web_cache.json`
    - `cache_dir` is passed as the final keyword argument to `ContextService.get_context(cache_dir=cache_dir)`
    - The `Path` import (`from pathlib import Path`) is already present in `session_orchestrator.py`; no additional imports required.
4.  **Validation Phase (Session Mode):**
    -   Resolves context paths from `session.context` and `turn.context`.
    -   **Context Harvesting**: Before validation, identifies unselected (pruned) context items and records them in `plan.metadata["pruned_context"]`. This ensures persistence even if the turn fails validation.
    -   Calls `PlanValidator.validate(plan, context_paths)`.
    -   If errors exist, triggers the **Automated Re-plan Loop**.
5.  **Context Assembly (with Cache):** When calling `ContextService.get_context()`, the `cache_dir` (session root path) is passed as `cache_dir` parameter to enable web content caching. URLs in session/turn context files are checked against the cache before network fetches.
6.  **Automated Re-plan Loop:**
    -   Generates a `report.md` in the current turn containing the validation errors.
    -   Triggers the replan via `SessionLifecycleManager.trigger_replan`, propagating the current `Plan` object.
    -   Calls `SessionService.transition_to_next_turn` with `is_validation_failure=True`, and extracts `pruned_context` from the plan metadata to ensure pruned files remain excluded from the next turn's manifest.
    -   Calls `PlanningService.generate_plan` for the new turn, using a structured feedback payload (Errors + Original Plan) as the user message. Relies on `PlanningService` defensive resolution to carry forward session history.
7.  **Planning Visibility:** Centralizes planning triggers to provide consistent UI feedback, extracting the Turn ID from the directory name and the agent name from metadata to display a progress message (e.g., `[01] Planning Turn with pathfinder...`) before LLM calls. The message is wrapped in `[cyan]` Rich style tags for consistent terminal coloring.
8.  **Telemetry Display:** After plan generation, retrieves metadata and displays model name, context token usage, and cumulative session cost to the user. The formatted telemetry strings are wrapped in `[dim]` Rich style tags to visually separate them as secondary information.
9.  **Auto-Naming:** Sessions created without a name (Turn 01) use a temporary timestamped name. The orchestrator automatically renames the session directory based on the slugified H1 title of the first generated plan. This allows the AI to suggest a meaningful name based on the actual content of the initial request.
10. **Report Persistence:** In Session Mode, the `ExecutionReport` is formatted and saved to `report.md` in the turn directory.
11. **Stateful Transition:** After saving the report, it calls `SessionService.transition_to_next_turn` to prepare the next stage of the session.

## 4. Data Contracts / Methods

### `execute(...) -> ExecutionReport`
-   **Description:** Implements the `IRunPlanUseCase`. If `plan_path` is present, it layers stateful session side-effects over the core execution.
-   **Cache Integration:** When in session mode (`plan_path` present), derives `cache_dir = str(Path(plan_path).parent.parent)` and passes it to `ContextService.get_context(cache_dir=cache_dir)` to enable web content caching.
-   **Single-Gather Contract (fallback-only re-gather):** `execute` accepts the planning-gathered `project_context` and forwards it to `ExecutionOrchestrator` (project context is gathered exactly once per turn by `PlanningService.generate_plan`). The in-execute re-gather is a fallback-only path, hit ONLY when `project_context is None` (e.g., the PENDING_PLAN resume branch passes `None`); the guard is an explicit identity check (`project_context is None`), never a truthiness check, so a provided context is never re-gathered. The fallback body (manifest resolution, agent-name patch, gather) is extracted into the private helper `_gather_fallback_context`.
-   **Mandatory Prune Invariant (Poka-Yoke):** `SessionPruningService.prune()` MUST run on EVERY session turn — on whichever context is present (the primary planning-gathered context OR the fallback re-gathered context) and BEFORE `_harvest_context()`. The call lives on the always-run path inside `execute()`; it is NEVER gated behind a performance/optional branch. A windows-startup-latency refactor had captured the sole `prune()` call inside the fallback-only `_gather_fallback_context` helper, silently disabling ALL pruning heuristics (the Turn-scope token budget AND `max_turns_retention`) on the primary session path, so `turn.context` grew unbounded past `turn_context_threshold`. **Gating discipline:** a performance gate may make *acquisition* (re-gathering) optional, but never a *side-effect* (pruning/harvesting). Regression coverage: `tests/suites/unit/core/services/test_session_primary_path_pruning.py` drives the primary path with a provided, oversized `project_context` and asserts the budget deselects the largest Turn-scope file.

### `resume(session_name: str, interactive: bool = True)`
-   **Description:** Implements the session state machine. Detects the state of the latest turn (EMPTY, PENDING_PLAN, COMPLETE_TURN) and triggers the appropriate action.
-   **Algorithm:**
    1.  Get current session state (EMPTY, PENDING_PLAN, COMPLETE_TURN).
    2.  **EMPTY**: Plan the new turn (using an injected `-m` message when present, else prompting) -> Resolve actual path via `SessionService` -> Call `execute`; an injected `-m` reply is also appended to the previous completed turn's report.
    3.  **PENDING_PLAN**: Consult the turn meta and the pending plan. An `awaiting_reply` turn (or a communication turn carrying an injected `-m` reply) is CONSUMED — the interrupted turn is finalized and the next turn is planned/executed from the reply (injected or interactively prompted); a NON-communication turn carrying an injected `-m` reply is executed in place with the reply SEEDED onto `plan.metadata["user_request"]` (parsed WITH its `plan_path`; `execute(plan=..., plan_path=...)` WITHOUT `message=`); otherwise the pending plan is re-executed bare (`execute(plan_path=...)`). The pending plan is parsed AT MOST ONCE on the resume path.
    4.  **COMPLETE_TURN**: Transition to next turn (appending a smart-fenced `## User Request` section when an injected `-m` reply is present) -> Plan the new turn (using the injected message when present, else prompting) -> Resolve actual path via `SessionService` -> Call `execute`.
- **Recursion Safety:** To prevent recursion loops and handle dynamic renaming, the state machine resolves the current turn's path from the `SessionService` after planning/renaming and delegates directly to `execute`.

## Console Visibility Helpers

Four helper functions are defined in this module to improve user visibility during session execution:

### `_print_initial_request(message, is_session)`
Prints the initial user request before the turn header/telemetry block.
- **Input**: `message` (Optional[str]), `is_session` (bool)
- **Behavior**: Only prints when `is_session=True` and `message` is non-empty.
- **Output**: `Initial Request:\n{message}\n`

### `_print_header_bar(plan, is_session)`
Prints the plan status emoji and title after the telemetry block, before action execution logs.
- **Input**: `plan` (Plan), `is_session` (bool)
- **Behavior**: Only prints when `is_session=True`. Extracts emoji from `plan.metadata["Status"]` using a local `_extract_status_emoji` helper that checks for emoji substrings (🟢, 🟡, 🔴). Falls back to empty string if no emoji found.
- **Note**: A local emoji extraction helper was implemented using simple substring containment (`if emoji in raw_status`) instead of importing `extract_status_emoji` from `textual_plan_reviewer_helpers.py` to maintain Hexagonal Architecture boundaries (core must not depend on adapters).
- **Output**: `{emoji} {title}` (no blank lines around it)

### `_print_user_message(message, is_session)`
Prints the user message after all actions execute.
- **Input**: `message` (Optional[str]), `is_session` (bool)
- **Behavior**: Only prints when `is_session=True` and `message` is non-empty.
- **Output**: `\nUser Message:\n{message}\n`

### `_print_message_from_teddy(content)`
Prints the agent's MESSAGE in the canonical presentation: a blank separator, a CYAN `--- MESSAGE from TeDDy ---` frame, then the message body (As-Built, 2026-10-02; Bug 54 / defect 4a).
- **Input**: `content` (str)
- **Behavior**: Always prints (the caller owns the gating). Uses `typer.secho` (stdout) so both display paths share one rendering.
- **Output**: `\n` + CYAN frame + body.
- **Consumers**: the orchestrator's pipeline MESSAGE print AND `SessionLifecycleManager._consume_awaiting_reply`'s `resume -p` no-message stop-again branch — the two paths compose this helper with `_print_header_bar` so their output is byte-identical and the framing literal is single-sourced (interior core helper; no `IUserInteractor` Port change).

All helpers are guarded at their call sites in `execute()`: `_print_initial_request` and `_print_user_message` are wrapped with `if is_session and message and message.strip():`, `_print_header_bar` is wrapped with `if is_session:`, and `_print_message_from_teddy` is invoked only on the pipeline MESSAGE path. This ensures no unnecessary function invocations occur in non-session or empty-message modes. Each helper also has internal guards as defense-in-depth.

## Pipeline MESSAGE Suppression (As-Built, 2026-10-01)

In pipeline mode (`pipeline=True`), a session turn whose plan is a communication turn ending with a non-empty MESSAGE action is NOT finalized: `finalize_turn` is skipped entirely (no `report.md`, no next-turn directory) and the current turn's `meta.yaml` is flagged with `awaiting_reply: true` via a load-modify-save over the turn-meta seam (`SessionService.load_turn_meta` / `save_turn_meta`). The report is still returned so the CLI loop's existing MESSAGE break fires and the `--- MESSAGE from TeDDy ---` terminal printing is preserved. Non-pipeline MESSAGE turns (interactive/YOLO) and pipeline turns without a MESSAGE keep the existing finalization behavior. MESSAGE-action detection iterates `report.action_logs` (see PROJECT.md Technical Debt: the iteration is duplicated with the empty-reply "4a" termination block; a shared detector is a Milestone 5 candidate).

The `resume` entry point threads an optional injected `message` (from `teddy resume -m`) through to `SessionLifecycleManager.resume` as an append-only keyword parameter, enabling the awaiting-reply and EMPTY/COMPLETE_TURN message-consumption paths without interactive prompting.

## `resume -m` PENDING_PLAN Handling (As-Built, 2026-10-03)

The `PENDING_PLAN` branch of `SessionLifecycleManager.resume` honors an injected `resume -m` reply on a NON-communication turn (plan.md present, report.md absent, no `awaiting_reply` flag) — the last remaining `-m` drop site after Bug 57 fixed the communication sub-branch. When a reply is supplied, the pending plan is parsed WITH its `plan_path` (preserving `Plan.is_session`/`Plan.plan_path`, which a path-less parse would drop because `execute(plan=...)` short-circuits `_resolve_plan`), the reply is seeded as `plan.metadata["user_request"] = message`, and `orchestrator.execute(plan=plan, plan_path=plan_path, ...)` is called WITHOUT `message=` (a forwarded `message` would WIN in the assembler over `plan.metadata["user_request"]`, discarding a TUI edit's harvest). An unparseable pending plan falls back to the unchanged bare re-execute path (catching `InvalidPlanError` precisely). The pending plan is parsed AT MOST ONCE on the resume path: `_parse_pending_plan(turn_path, plan_path, message)` performs the single WITH-path parse (returning `None` without parsing when no reply is injected, so the `awaiting_reply` short-circuit and the bare re-execute stay parse-free), and that one `Plan` is threaded through BOTH the consumption decision (`_should_consume_awaiting_reply(turn_meta, plan)`) and the consumption synthesis (`_consume_awaiting_reply(..., plan=plan)` → `_synthesize_message_report(..., plan=plan)`). Verified end-to-end for the `-y` facet by `tests/suites/acceptance/test_pipeline_message_and_resume_flow.py`.
