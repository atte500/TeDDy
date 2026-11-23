# Slice: Session-Root-Gated Context Partition
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc fix for [Bug 82](../debugging/82-session-scope-read-other-session.md))
- **Depends On:** None
- **Specs:** None pinned
- **Prototype:** N/A — behaviour verified in [replica_context_service.py](/spikes/debug/session-scope-read-other-session/replica_context_service.py)
- **Component Docs:** [ContextService](/docs/architecture/core/services/context_service.md), [IGetContextUseCase](/docs/architecture/core/ports/inbound/get_context_use_case.md), [ProjectContext](/docs/architecture/core/domain/project_context.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `session-scoped-context`

## Goal
A path read from another session renders under `## Resource Contents` (and in the TUI's scope group) instead of being printed as the current session's own `## Session History`, while a session's own `initial_request.md`/`plan.md`/`report.md` keep rendering as history.

## Context
Findings from static reading, the case file, and the MRE.

- `ContextService._format_content` (`src/teddy_executor/core/services/context_service.py:396-405`): flattens every scope into one ordered list and splits it with `is_session_file_path`. Nothing in the split considers which session is rendering.
- `ContextService._format_session_history` (`:513-538`): keeps every path whose `get_session_history_display_name` is non-`None`, sorts with `get_session_history_sort_key`, and emits `### <display name>` blocks. Unrecognized session-shaped paths are dropped from both sections.
- `src/teddy_executor/core/utils/markdown.py:232-274`: four shape-only predicates. `is_session_file_path` is a bare `"sessions/" in path` substring test; `get_session_history_display_name` matches `sessions/[^/]+/(\d+)/{plan,report}.md$` plus any path containing `initial_request.md`; `is_session_history_path` delegates to it; `get_session_history_sort_key` re-parses the turn number.
- `IGetContextUseCase.get_context` (`src/teddy_executor/core/ports/inbound/get_context_use_case.py`): seven parameters, no session identity.
- `ProjectContext` (`src/teddy_executor/core/domain/models/project_context.py`): no `session_root` field; the TUI receives only this DTO.
- Production call sites, each already holding a root: `session_orchestrator.py:458/476` (`str(Path(plan_path).parent.parent)`), `planning_service.py:80` (`str(Path(turn_dir).parent)`), `session_cli_handlers.py:1438` via `detect_session_context()`, which returns `Path.cwd().parent` inside a session and `None` outside.
- `adapters/inbound/textual_plan_reviewer_helpers.py`: the TUI reuses the same predicates for the Session/Turn exclusion (`:164`), History grouping and sort (`:172-176`), item labels (`:120-122`), and the token-budget split (`:83-91`).
- Reproduction: `01-foreign-session-read-renders-as-own-history-mre.py` renders a foreign `03/report.md` as `### Turn 3: Report` inside `## Session History` on unaltered `src/` (exit 1) and under `## Resource Contents` with `--replica` (exit 0).
- Deliberate deviation from the replica: the gate matches the session directory name — the root's final path component — as a complete path segment of the candidate path, instead of comparing path prefixes. The replica's textual prefix compare only works when the context path and the root share a relative/absolute form, and the two sides are produced by independent resolution paths: the three real callers pass `Path(...)`-derived roots while context paths arrive as `.teddy/sessions/...` or as absolute paths from manifest and directory expansion. Whole-segment matching is form-agnostic, immune to an earlier `sessions/` component in an absolute path, needs no filesystem access, and keeps tests hermetic.
- No Harness and no Wiring deliverable: the change adds no entry point, driver, observer, or shared fake. The outermost seam under test is `ContextService.get_context`, which the existing `service` fixture already drives.
- The CLI path inside a session stays covered by existing acceptance tests; the regression pin lives at the service seam.

## Scenarios

> As an agent reading a file from another session, I want that file rendered as ordinary resource content so that the current session's history stays truthful.

```gherkin
Given a context assembled for session "my-session"
And "my-session/01/plan.md" and "my-session/01/report.md" in the Session scope
And "other-session/03/report.md" in the Turn scope
When the context is rendered with session_root "my-session"
Then "my-session/01/plan.md" and "my-session/01/report.md" appear under "## Session History"
And "other-session/03/report.md" appears under "## Resource Contents"
And "## Session History" precedes "## Resource Contents"
```

> As a user reviewing the plan, I want the TUI tree to group the foreign file with the turn's resources so that the History node lists only this session's turns.

```gherkin
Given a ProjectContext whose session_root is "my-session"
And items for "my-session/01/report.md" and "other-session/03/report.md"
When the context tree is built
Then the History node lists "Turn 1: Report" only
And the Turn group lists the other-session path
```

## Edge Cases
- **Foreign plan or report**: If a `sessions/<other>/<NN>/{plan,report}.md` path is supplied with a root, then it renders under `## Resource Contents`, because history membership requires the own-root segment.
- **Foreign initial request**: If `sessions/<other>/initial_request.md` is supplied with a root, then it renders under `## Resource Contents`, because the `initial_request.md` display name is gated by the own-root segment.
- **Workspace path containing a `sessions/` segment**: If `src/sessions/handler.py` is supplied with a root, then it renders under `## Resource Contents`, because it is not under the own root.
- **No root supplied**: If `session_root` is `None`, then the partition is byte-identical to today's behavior, because every existing caller and test keeps working through the default.
- **Root and path form mismatch**: If the root is absolute and the context path is relative (or the reverse), then classification is unchanged, because comparison matches the session directory name as a whole path segment rather than a path prefix.
- **Absolute path with an earlier `sessions/` directory**: If the repository itself lives under a directory named `sessions` (for example `/home/user/sessions/repo/.teddy/sessions/own/01/plan.md`), then the path is still recognized as own history, because matching uses the session directory name as a whole segment rather than the first `sessions/` occurrence.
- **Root with trailing separator or `./` prefix**: If the root arrives as `.teddy/sessions/own/` or `./.teddy/sessions/own`, then it classifies identically to the canonical form.
- **Continuation session names**: If the root is `...-feat-x-2` and a path belongs to `...-feat-x`, then the path is foreign, because the segment match is exact and never a prefix match.
- **Unrecognized path under the own root**: If `.teddy/sessions/own/01/meta.yaml` is supplied, then it stays non-rendered, because no display name matches and this matches current behavior.
- **Directory expansion ordering**: If own history paths arrive through a directory expansion rather than an explicit list, then they still classify as history, because the gate reads only the path string.
- **Sorting**: If history paths are retained, then `get_session_history_sort_key` ordering is unchanged, because sorting is independent of session membership.

## Key Unknowns
None open. Every question the case file raised is resolved and re-verified against `src/`:
- [x] [Domain] Is a session-root gate sufficient to separate own history from foreign reads? Resolved by the replica: yes, and it does not suppress the section it corrects.
- [x] [Technical] Does the bookkeeping layer leak READ paths into `session.context`? Resolved: no, the preserve arm passes only the turn's own `plan.md`/`report.md`, so the defect is render-time only.
- [x] [Technical] Can scope alone discriminate? Resolved: no, the session's own artifacts arrive via the `Turn` scope in non-preserved turns.
- [x] [Technical] Can the gate compare path prefixes as the replica does? Resolved: no, the callers' roots and the context paths are resolved independently and differ in relative/absolute form, so the gate matches the session directory name as a whole path segment instead.
- [x] [Functional] Does the TUI need a second plumbing route for the root? Resolved: no, carrying `session_root` on `ProjectContext` reaches every TUI consumer.

## Impact
1. `[EXTEND]` `src/teddy_executor/core/utils/markdown.py` — add `is_own_session_path(path, session_root)`; add an optional `session_root` parameter to `get_session_history_display_name` and `is_session_history_path`. Defaults preserve today's shape-only behavior.
2. `[EXTEND]` `IGetContextUseCase.get_context` — add `session_root: Optional[str] = None` as the last keyword parameter.
3. `[EXTEND]` `ProjectContext` — add `session_root: Optional[str] = None`.
4. `[EXTEND]` `ContextService.get_context` / `_format_content` — accept the root, gate the partition on it, and carry the resolved root on the returned DTO.
5. `[MIGRATE]` `SessionOrchestrator`, `PlanningService`, `handle_context_gathering` — pass the root each already computes; the CLI resolves it through a sibling of `detect_session_context()` and passes `None` outside a session.
6. `[MIGRATE]` `textual_plan_reviewer_helpers.py` — consume `project_context.session_root` for the Session/Turn exclusion, History grouping, item labels, and the history token split.
7. `[MIGRATE]` `tests/suites/unit/core/utils/test_markdown_utils.py`, `tests/suites/unit/core/services/test_context_service.py`, `tests/suites/unit/adapters/inbound/test_reviewer_app_context_previews.py` — extend existing coverage additively; the roughly forty existing `get_context(` calls stay green through the default.

`is_session_file_path` is deliberately kept coarse and public: it remains the "under a `sessions/` segment" test that the gate layers on.

## Deliverables
- [x] **Interface** - `is_own_session_path` plus the optional `session_root` parameters in `core/utils/markdown.py`; `session_root` on `IGetContextUseCase.get_context` and on `ProjectContext`. Unit tests pin the predicate: own path, foreign path, workspace path with a `sessions/` segment, `None` root legacy behavior, form mismatch, trailing separator, continuation-name collision, and an absolute path whose earlier directory is also named `sessions`.
- [x] **Core** - `ContextService.get_context` threads `session_root` into `_format_content`, partitions on `is_own_session_path`, and carries the root on the DTO. Regression unit test in `tests/suites/unit/core/services/test_context_service.py` supplies an own-history path and a foreign-session path together with a root and asserts own history stays under `## Session History` while the foreign path renders under `## Resource Contents`.
- [x] **Migration** - the three production call sites pass their root (and the CLI passes `None` outside a session); the TUI helpers consume `project_context.session_root` for the exclusion, History grouping, labels, and token split; extend the MRE with a mode that passes the session root to the loaded module so it doubles as a post-fix check; update caller tests additively.
- [ ] **Refactor** - consolidate the path normalization and session-segment extraction shared by the four predicates into one private helper in `core/utils/markdown.py`, and route `ContextService` through the shared predicate only. No new tests; the full suite stays green.

## Implementation Notes

### Interface deliverable
- Added `_session_directory_name` and `is_own_session_path` to `src/teddy_executor/core/utils/markdown.py`. `is_own_session_path` guards on the coarse `is_session_file_path`, then compares the root's final path component against the candidate path's segments. With no root supplied it returns the coarse result unchanged, so the legacy partition stays byte-identical.
- Widened `get_session_history_display_name` and `is_session_history_path` with an optional `session_root`. The gate runs first: when a root is supplied and the path is foreign, the display name is `None` and the path is not history. With no root the two helpers behave exactly as before.
- Added the defaulted `session_root: Optional[str] = None` keyword to `IGetContextUseCase.get_context` and the defaulted `session_root` field to `ProjectContext`. Neither change alters an existing caller or a direct DTO construction.
- Gate decision verified by test: whole-segment matching of the session directory name handles absolute-vs-relative roots, a trailing separator, a `./` prefix, an earlier `sessions/` directory in an absolute path, and exact (never prefix) continuation-name matching.
- Regression pin: `tests/suites/unit/core/utils/test_markdown_utils.py::test_session_root_gate_separates_own_history_from_foreign_paths`.
- Deferred: `is_session_file_path` still performs a raw `"sessions/" in path` substring test with no backslash normalization; folding the shared normalizer is scheduled under the Refactor deliverable.
- The widened port declaration carries `# noqa: PLR0913 - inbound-port seam; additive keyword`. The eight-keyword surface is the shared inbound seam, and collapsing it into a parameter object would break the roughly forty callers the additive default exists to protect; the implementation already carries the same bypass. A `per-file-ignores` entry would suppress the rule far beyond this one finding.

### Core deliverable
- `ContextService.get_context` accepts `session_root`, forwards it to `_format_content`, and stamps it on the returned `ProjectContext`. `_format_content` grew to five non-`self` parameters, exactly at the `PLR0913` floor, so no bypass was needed.
- `_format_content` partitions with `is_own_session_path(p, session_root)`; the workspace bucket is the complement of the session bucket, so a foreign session path and a workspace path carrying a `sessions/` segment both fall through to `## Resource Contents` instead of being dropped from both sections.
- Swapped the now-unused `is_session_file_path` import for `is_own_session_path`; a grep confirmed the coarse predicate had only its import plus the two former partition lines, so nothing was orphaned.
- `_format_session_history` was left unchanged: the gated partition already excludes foreign paths from its input, so its display-name filter remains correct.
- Regression pin: `tests/suites/unit/core/services/test_context_service.py::test_get_context_renders_foreign_session_read_as_resource_content`, covering own `plan.md`/`report.md` under `## Session History`, the foreign `03/report.md` under `## Resource Contents`, the workspace `src/sessions/handler.py` under `## Resource Contents`, and the resolved root on the DTO.
- Deferred to the Migration deliverable: the three production call sites and the TUI helpers still pass no root, so they keep the byte-identical legacy partition through the `None` default.

### Migration deliverable
- `PlanningService.generate_plan` derives `session_root = str(Path(turn_dir).parent)` once and passes it as both `cache_dir` and `session_root`, so the web-cache directory and the history gate read one expression instead of two derivations.
- `SessionOrchestrator._gather_fallback_context` passes `session_root=cache_dir`; `cache_dir` was already `str(Path(plan_path).parent.parent)`, the session directory, so no new derivation was introduced.
- `session_cli_handlers.detect_session_root()` is a sibling of `detect_session_context()`: it returns `str(Path.cwd().parent)` only when the three-file session gate matches and `None` outside a session. The gate is shared rather than re-implemented, and `handle_context_gathering` passes the result into `get_context`. The scope map `detect_session_context()` returns could not be reused because `--only`/`-c` override it.
- `populate_context_detail` reads `app.project_context.session_root` and gates the Session, Turn, and History token splits with `is_session_history_path(path, session_root)`, so a foreign read's tokens count under neither Session nor Turn nor History.
- `format_context_item_label` gained a defaulted `session_root` so its direct callers stay green while the rooted callers forward the DTO value; `get_session_history_display_name(path, session_root)` then returns `None` for a foreign read, which renders the raw path instead of a misleading `Turn N: Report` label.
- `build_context_section` reads the DTO root once, narrows the scope-group exclusion from `is_session_file_path` to `is_own_session_path(item.path, session_root)`, and gates the History grouping with `is_session_history_path(path, session_root)`; both leaf-label calls forward the root.
- The exclusion narrowing is load-bearing: the coarse predicate hid a foreign-session read from its own scope group, so the path rendered nowhere at all. With the own-root gate it stays in the group it arrived in.
- `textual_plan_reviewer_logic.refresh_node_logic` forwards the DTO root when relabelling a context item, so a toggled foreign read does not fall back to the legacy label.
- `_format_session_history` was left unchanged: the gated partition already excludes foreign paths from its input, so its root-less display-name filter remains correct.
- Caller tests were extended additively rather than added: the planning assertion gains `session_root=str(Path("sessions/S1/02").parent)`, the orchestrator test asserts `session_root == cache_dir` on the gathered kwargs, and the reviewer History test gains a foreign-session `03/report.md` plus the own root, asserting the foreign path renders in the Turn group and never as `Turn 3: Report` under History.
- MRE: `--fixed` passes `session_root=CURRENT_SESSION` to the loaded production module and labels the run `fixed`; the implementation label distinguishes `replica`, `fixed`, and `production`. The production run still reproduces the bug (`legacy_exit=1`, `VERDICT: BUG REPRODUCED`), and the fixed run reports `VERDICT: OK - foreign READ lands in ## Resource Contents` (`fixed_exit=0`).
- Evidence: `53 passed` across the five caller and helper modules, `ruff check` clean, and the full suite at `2314 passed, 5 skipped`.
- Still deferred: `format_context_item_label` reaches the display-name helper, which itself calls `is_session_file_path` with no backslash normalization; the shared normalizer lands with the Refactor deliverable.

## Verification
1. **Post-fix rendering of a foreign read:**
   Run `uv run python spikes/debug/session-scope-read-other-session/01-foreign-session-read-renders-as-own-history-mre.py --fixed`.
   Verify the verdict line reads `VERDICT: OK - foreign READ lands in ## Resource Contents`, the foreign marker sits under `## Resource Contents`, and the own marker stays under `## Session History`.
2. **Legacy behavior without a session root:**
   Run `uv run python spikes/debug/session-scope-read-other-session/01-foreign-session-read-renders-as-own-history-mre.py`.
   Verify the verdict still reads `VERDICT: BUG REPRODUCED`, confirming the no-root fallback is unchanged.
3. **TUI grouping inside a real session:**
   Start a session with `teddy start`, have the agent `READ` a file from another session under `.teddy/sessions/`, then open the plan reviewer and select the Context root.
   Verify the foreign path is absent from the `History:` node, present under the scope group it arrived in, and that `Hist` token totals exclude it.
