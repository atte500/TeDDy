# Bug: READ of Another Session's Files Renders as Own Session History
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** None pinned yet

## Symptoms

**Expected:** When an agent READs files that belong to a different session (for example `.teddy/sessions/<other>/03/report.md`), those paths contribute to the current turn's transient working set (`turn.context`) only.

**Actual:** The read path is persisted in the current turn's working set (`turn.context`) as intended, but at render time it is bucketed by path shape alone and printed inside the current session's `## Session History` section — the section that lists the session's own `plan.md`/`report.md` history — instead of under `## Resource Contents`. Because the path stays in the context chain, every later turn of that session renders it as its own history again.

**Minimal reproduction:** [01-foreign-session-read-renders-as-own-history-mre.py](/spikes/debug/session-scope-read-other-session/01-foreign-session-read-renders-as-own-history-mre.py) drives the real `ContextService` with the current session's `initial_request.md`/`plan.md`/`report.md` in the `Session` scope and a foreign session's `03/report.md` in the `Turn` scope.

~~~~
uv run python spikes/debug/session-scope-read-other-session/01-foreign-session-read-renders-as-own-history-mre.py
~~~~

Observed on unaltered `src/`: the foreign report renders as `### Turn 3: Report` inside `## Session History`, exit code `1`. With `--replica`: the same path renders under `## Resource Contents` while own history stays in `## Session History`, exit code `0`.

## Context & Scope

### Regressing Delta

Two commits on 2026-05-21 introduced the defect:

- `5f08718f2` — added `get_session_history_display_name`, `is_session_file_path`, `is_session_history_path`, and `get_session_history_sort_key` to `src/teddy_executor/core/utils/markdown.py:232-274`. Each takes a path only: the display-name regex `sessions/[^/]+/(\d+)/plan.md$` matches any session segment, and `is_session_file_path` is a bare `"sessions/" in path` substring test. `49aaeb327` (2026-06-15) later touched only the `Turn N: Report` return line.
- `18131caf7` — added the scope-flattening partition in `ContextService._format_content` (`src/teddy_executor/core/services/context_service.py:396-405`): every scope is flattened into one list and split with `is_session_file_path`, with no notion of which session is rendering. `f2518ccc2` (2026-06-08) later added the `## Session History` prepend and the `_format_session_history` call.

Consumers of the shape-only classifier:

- `src/teddy_executor/core/services/context_service.py:513-538` — `_format_session_history` keeps every path whose display name is non-None and prints the block under `## Session History`.
- `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py:83-91, 120-122, 164-176` — the TUI reuses the same predicates for its Session/Turn exclusion, its History grouping, its item labels, and its token-budget split.

The bookkeeping path is not at fault: `SessionService._apply_single_log_effect` adds the READ path to the turn's working set, and the preserve arm passes only `plan.md`/`report.md` to `session.context`.

### Environmental Triggers

None identified. The behavior follows from path shape alone and is therefore platform-independent; it reproduces with any session directory present. `auto_pruning.preserve_message_turns` is irrelevant to this rendering decision.

### Ruled Out

- **`session.context` persistence of READ paths.** `SessionService.transition_to_next_turn` writes the working set to the next `turn.context` unconditionally; the preserve arm appends exactly `{plan.md, report.md}` to `session.context`. No code path writes an arbitrary READ path to `session.context`.
- **`_is_preserved_turn` heading detection.** Both arms of the transition carry the same paths to `turn.context`; preservation only decides extra session-scope entries for the turn's own artifacts.

## Diagnostic Analysis

### Causal Model

Verified by code reading and by the MRE above:

1. A READ action contributes its `resource` path to the current turn's working set only when the status is SUCCESS and no `Lines`/`lines` parameter is present (`SessionService._apply_single_log_effect`).
2. That working set is written to the next turn's `turn.context` unconditionally. The preservation branch adds only the turn's own `plan.md`/`report.md` to the prune-exempt `session.context`; it never routes READ paths there.
3. At context-assembly time, `ContextService._format_content` collects every path from all scopes into one list and splits it with `is_session_file_path` — a bare `"sessions/" in path` substring test. Nothing in the split considers which session is rendering.
4. The session bucket goes to `_format_session_history`, which keeps paths whose `get_session_history_display_name` is non-None. That helper matches the shape `sessions/<any>/<NN>/{plan,report}.md` or any path containing `initial_request.md`, so a foreign session's history file is indistinguishable from the current session's own.
5. Consequence: a path read from another session is rendered under the current session's `## Session History` with a display name like `Turn 3: Report`, and is never offered to `## Resource Contents`. The MRE reproduces this on production code, and the replica confirms that gating the partition on the rendering session's root is both sufficient and non-destructive.

### Discrepancies

- [x] A READ of a foreign session's files is expected to render as ordinary resource contents, but it renders under the current session's `## Session History` (Resolved: the partition and the classifier are both session-agnostic; the MRE reproduces the misplacement and the replica proves a session-root gate fixes it).
- [x] The bookkeeping layer was expected to leak READ paths into `session.context` (Resolved: it does not — the preserve arm passes only the turn's own `plan.md`/`report.md`, and the working set always goes to `turn.context`).
- [x] The manifest-driven sectioning discussed in `session.context`/`turn.context` was expected to be relevant (Resolved: irrelevant — the fault is render-time bucketing by path shape).
- [x] Neither the renderer nor the classifier has any notion of "own session", so no correct classification was possible with the information previously reaching `_format_content` (Resolved: the rendering session's root must be threaded from the caller; the replica proves it is sufficient).
- [x] Whether scope alone can act as the discriminator (Resolved: it cannot — in a non-preserved turn the session's own `plan.md`/`report.md` arrive via the `Turn` scope alongside the foreign read).

### Investigation History

1. Grepped for writers of `session.context` and `turn.context`; observed that `SessionService` owns both, with an explicit preservation branch, while the inbound CLI handler only resolves the paths for display. Concluded the routing decision lives in `SessionService`.
2. Grepped for `preserve` across services and ports; observed two preservation entry points (`transition_to_next_turn` and `preserve_turn_in_session_context`) sharing `_is_preserved_turn`, and that READ paths are filtered only by action status and the `Lines` parameter. Localized the defect surface to the routing decision rather than path extraction.
3. Read the full `_is_preserved_turn` body and the transition ordering; observed that the preserve arm passes exactly `{plan_md_path, report_md_path}` to `_append_to_session_context` while the working set is written to the next `turn.context` in both arms. This contradicted the bookkeeping hypothesis and retired it.
4. Grepped for "session history"; discovered `## Session History` is produced by `ContextService._format_session_history` and that "session history" is a pure path classifier (`get_session_history_display_name`). Reconciled that finding with the user's wording.
5. Read the classifier helpers and the `_format_content` partition; observed that both are session-agnostic — the split is a substring test and the display name matches any session segment. This is the current working model.
6. Built and ran the MRE against unaltered `src/`; observed the foreign report rendered as `### Turn 3: Report` inside `## Session History`, which confirmed the code-read model empirically.
7. Built `replica_context_service.py` with a `session_root` parameter and an `_is_own_session_path` gate; re-ran the same MRE with `--replica`; observed the foreign path move to `## Resource Contents` while own history stayed under `## Session History`. The gate is sufficient and does not suppress the section it corrects.
8. Audited consumers: `git blame` pinned the classifier to `5f08718f2` and the partition to `18131caf7`; three production `get_context` call sites exist and every one already holds the session root as `cache_dir`; the TUI derives its History group, labels, and token split from `ContextItem.path` alone, with no session identity in reach.
9. Confirmed the latent sibling defect: `is_session_file_path` matches any `sessions/` segment, so a workspace path such as `src/sessions/handler.py` is partitioned out and then dropped from both sections because no display name matches it. The replica's root gate neutralizes it when a root is supplied; the no-root fallback preserves today's behaviour.

## Solution

### Root Cause

Verified and proven. Session-history classification was session-agnostic: `ContextService._format_content` flattened every scope into one list and split it with `is_session_file_path` (a `"sessions/"` substring test), then `get_session_history_display_name` matched `sessions/<any>/<NN>/{plan,report}.md` by shape alone. A path read from another session therefore landed in the current session's `## Session History` instead of `## Resource Contents`.

The fix is a session-root gate on the partition: pass the rendering session's root into `get_context`, treat a path as own history only when it lives under that root, and route every other path — including foreign session files — to `## Resource Contents`. When no root is supplied (no session in scope, as with `teddy context` outside a session), the legacy partition stays in force, so the change is backward compatible.

Proven in the sandbox replica ([replica_context_service.py](/spikes/debug/session-scope-read-other-session/replica_context_service.py)), not applied to `src/`: the change crosses a shared inbound port, the `ProjectContext` DTO, three production call sites, and the TUI, which exceeds direct-resolution scope.

### Affected Components

- `IGetContextUseCase.get_context` (`src/teddy_executor/core/ports/inbound/get_context_use_case.py`): add an optional `session_root: Optional[str] = None` keyword. The default keeps every existing caller and test working unchanged.
- `ContextService.get_context` / `_format_content` (`src/teddy_executor/core/services/context_service.py`): accept `session_root` and gate the partition on it. Add `_is_own_session_path(path, session_root)`; keep `is_session_file_path` as the coarse "under `sessions/`" test and fall back to the legacy partition when `session_root is None`.
- `ProjectContext` (`src/teddy_executor/core/domain/models/project_context.py`): carry the resolved `session_root` as an optional field, so the TUI — which receives only the DTO — gates its groupings with the same discriminator instead of needing a second plumbing route. This is the recommended path; threading the root into `TextualPlanReviewer` instead is equivalent but duplicates the fact.
- Production call sites, all of which already hold the session root:
    - `src/teddy_executor/core/services/session_orchestrator.py:472` — `Path(turn_dir).parent`, currently passed as `cache_dir`.
    - `src/teddy_executor/core/services/planning_service.py:75` — `Path(plan_path).parent.parent`, currently passed as `cache_dir`.
    - `src/teddy_executor/adapters/inbound/session_cli_handlers.py:1438` — `Path.cwd().parent` per `detect_session_context`, and `None` when no session is detected.
- `adapters/inbound/textual_plan_reviewer_helpers.py`: pass the DTO's `session_root` into `is_session_history_path` / `get_session_history_display_name` / `get_session_history_sort_key` for the History group (`:164-176`), the item labels (`:120-122`), and the history token split (`:83-91`).
- Tests pinning current behaviour: `tests/suites/unit/core/utils/test_markdown_utils.py`, `tests/suites/unit/core/services/test_context_service.py`, `tests/suites/unit/adapters/inbound/test_reviewer_app_context_previews.py`, plus the 40 `get_context(` calls across nine test modules, which keep working through the default.

Required regression test: a unit test in `tests/suites/unit/core/services/test_context_service.py` that supplies both an own-history path and a foreign-session path together with a `session_root`, asserting the own path stays in `## Session History` and the foreign path renders under `## Resource Contents`. No deterministic lint rule is warranted: the defect is a single-site information gap, and a behavioural test pins it far more precisely than a structural check could.
