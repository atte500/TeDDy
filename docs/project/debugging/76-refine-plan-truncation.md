# Bug: Plan Refinement Truncated by the READ Line Cap

- **Status:** Unresolved
- **Milestone:** N/A (ad-hoc bug fix)
- **Vertical Slice:** [Slices/00-13-plan-truncation-decoupling.md](/docs/project/slices/00-13-plan-truncation-decoupling.md)
- **Specs:** N/A

## Symptoms

When a long plan is viewed, refined, resumed, or executed, it is cut off after the first `read.max_lines` lines (default 1000) and the following banner is appended at the end of the truncated content:

`[Content truncated: Showing first 1000 of 51503 lines. Use the 'Lines' parameter to read specific line ranges (e.g., '2-25').]`

Expected: viewing or refining a plan shows the complete plan (or truncates at a plan-appropriate limit) without the READ-tool hint.

Actual: the plan is truncated at the READ tool's `read.max_lines` cap and the READ-action hint is appended.

Minimal reproduction:

1. Produce a plan whose file exceeds `read.max_lines` (default 1000 lines).
2. Open the plan for viewing/refinement from the TUI plan reviewer (`view_plan_handler`).
3. The editor shows only the first 1000 lines followed by the "Use the 'Lines' parameter" banner.
   The same truncation affects plan parsing on execute/resume because those paths also read the plan via `read_file`.

## Context & Scope

### Regressing Delta

Not a discrete regression: the plan-read call sites have always routed through the READ-truncating `read_file` method.

- `src/teddy_executor/adapters/outbound/local_file_system_adapter.py:289` — `read_file` truncates via `truncate_lines(content, max_lines=self.max_read_lines, direction="head", action_type="read")`.
- `src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py:274` — `view_plan_handler` reads the plan via `read_file` for viewing/refinement.
- `src/teddy_executor/core/services/session_orchestrator.py:552` (`_prepare_plan_parsing`) and `:595` (`_validate_plan_with_context`) — read the plan via `read_file` when no `plan_content` is supplied.
- `src/teddy_executor/core/services/execution_orchestrator.py:249` — execute path reads the plan via `read_file`.
- `src/teddy_executor/core/services/session_lifecycle_manager.py:400` — resume path reads the plan via `read_file` for parsing.
- `src/teddy_executor/core/services/session_service.py:339` — `_is_preserved_turn` reads the plan via `read_file` to detect `## Message`.

Cap definition: `src/teddy_executor/core/domain/models/config_schema.py:42` (`max_lines: int = 1000` in the read settings), consumed as `LocalFileSystemAdapter.max_read_lines`.

### Environmental Triggers

Any plan file longer than `read.max_lines` (default 1000). No OS or environment dependency.

### Ruled Out

- `ContextService._format_session_history` / session-history display — it consumes `read_files_in_vault`, which explicitly bypasses `read.max_lines`, so history display is not the culprit.
- `MarkdownPlanParser._truncate_plan_content` — trailing-section write-back during parse, unrelated to the banner.

## Diagnostic Analysis

### Causal Model

`LocalFileSystemAdapter.read_file` is the only production path emitting the `[Content truncated: ... Use the 'Lines' parameter ...]` banner. It calls `truncate_lines(..., direction="head", action_type="read")`, which keeps the first `max_read_lines` lines and appends the READ hint after them. Plan reads for refinement, viewing, parsing, execution, and turn-preservation all call `read_file`, so a long plan is truncated and stamped with a READ-tool hint even though the reader is not a user READ action and cannot use the `Lines` parameter. `read_files_in_vault` (context assembly) bypasses the cap, so the plan is intact in the context payload but truncated wherever it is re-read as a single file.

### Discrepancies

- [ ] Plan viewing/refinement truncates a long plan at `read.max_lines` and appends the READ hint.
- [ ] Plan parsing on resume/execute consumes truncated content; `_write_back_session_plan` can then persist the truncated content back to disk.
- [ ] `_is_preserved_turn` can miss a `## Message` beyond line 1000, so a message turn is not preserved.
- [x] Session-history display does not truncate (Resolved: it uses `read_files_in_vault`, which bypasses the cap).

### Investigation History

1. Searched for the banner text; found it composed by `get_truncation_hint()` in `core/utils/string.py:279-295` and emitted only by `truncate_lines()`.
2. Enumerated `truncate_lines` call sites; found two production callers: `local_file_system_adapter.read_file` and `shell_adapter`.
3. Traced the cap to `read.max_lines` (default 1000) in `config_schema.py:42`, consumed as `LocalFileSystemAdapter.max_read_lines`.
4. Inspected session-history assembly; found it uses `read_files_in_vault`, which bypasses the cap, ruling out context/history display.
5. Enumerated plan reads; confirmed the TUI viewer, `session_orchestrator`, `execution_orchestrator`, `session_lifecycle_manager`, and `session_service` read plans via the truncating `read_file`.

## Solution

### Root Cause

Verified root cause: plan content read through `IFileSystemManager.read_file` inherits the READ-tool truncation (`read.max_lines`, default 1000) and the READ-action hint. Because plan refinement/viewing/parsing re-reads the plan file through `read_file`, long plans are truncated and stamped with the inappropriate "Use the 'Lines' parameter" hint. No fix has been applied yet; this case file establishes the verified mechanism for the Debugger.

Proposed fix shape (approved 2026-11-03):

- Add a configurable `plan.max_lines` setting in the config layer, default `5000`.
- Correctness reads (`_prepare_plan_parsing`, `_validate_plan_with_context`, `_is_preserved_turn`, resume/synthesis) switch to `read_raw_file` so plans are never truncated for parsing or marker detection.
- Display reads (TUI viewer/refinement) truncate at `plan.max_lines` with a hint-less plain notice `[Showing first N of M lines.]`; the "Use the 'Lines' parameter" hint is dropped.
- Keep truncation behavior for long plans; only decouple from `read.max_lines` and remove the READ-tool hint.

### Affected Components

- `LocalFileSystemAdapter.read_file` / `truncate_lines` / `get_truncation_hint`: need a plan-specific, hint-less, separately capped truncation path.
- `textual_plan_reviewer_previews.view_plan_handler`: read the plan via the new path.
- `session_orchestrator._prepare_plan_parsing` and `_validate_plan_with_context`: read the plan via the new path.
- `execution_orchestrator` plan resolution: read the plan via the new path.
- `session_lifecycle_manager` plan synthesis: read the plan via the new path.
- `session_service._is_preserved_turn`: read the plan via the new path (also fixes the `## Message`-beyond-1000 correctness hazard).
- `config_schema`: add a `plan.max_lines` setting (default `5000`).
