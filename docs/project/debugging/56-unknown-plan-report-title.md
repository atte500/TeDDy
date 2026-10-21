# Bug: Unknown Plan Report Title on Structural Parse Failure
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [report-format.md](/docs/project/specs/report-format.md)

## Symptoms
A session turn whose plan H1 parses still writes `# Execution Report: Unknown Plan` to `report.md` when the plan parser raises a structural error elsewhere in the document.

Expected: the report title carries the plan H1 text.
Actual: the report title falls back to the `"Unknown Plan"` sentinel even though the raw content holds a valid H1.

Reproduction: in session mode, run a plan whose H1 is valid and whose `## Action Plan` section is missing. The parser extracts the H1, then `validate_plan_structure` raises `InvalidPlanError`. The structural replan branch runs, and the failure report renders `Unknown Plan`.

## Context & Scope
### Regressing Delta
- `097bda62` (2026-04-22, `feat(core): extract SessionLifecycleManager from SessionOrchestrator`) introduced the `title: str = "Unknown Plan"` default on `SessionLifecycleManager.trigger_replan`.
- `f4bc0699` (2026-04-23, `refactor(core): revert architecture to synchronous and fix test harness`) touched the same literal.
- At HEAD, `SessionOrchestrator._prepare_plan_parsing` calls `trigger_replan` at the missing-file branch and the parse-exception branch without a `title` argument.

### Environmental Triggers
- Session mode only: `plan_path` resolves inside `.teddy/sessions/` and a sibling `meta.yaml` exists.
- A plan document with a parseable H1 and a structural fault that raises out of `MarkdownPlanParser.parse`.

### Ruled Out
- The report formatter: its fallback literal is `"Untitled Plan"`, not the observed `"Unknown Plan"`.
- The logical validation path: `_handle_logical_validation_errors` forwards `plan.title` and `plan.rationale`.
- The plan parser success path: it extracts the H1 into `Plan.title` through `get_child_text`.
- Stored session artifacts: no `report.md` on disk renders the literal; the matches quote the bug text inside an embedded user request.
- `_parse_and_handle_structural_errors`: it is unreferenced dead code, so it cannot be the live call site.

## Diagnostic Analysis
### Causal Model
1. `SessionOrchestrator.execute` detects session mode and calls `_prepare_plan_parsing`.
2. `_prepare_plan_parsing` passes the raw content to `MarkdownPlanParser.parse`.
3. The parser normalizes the content, extracts the H1 into `Plan.title`, and then raises `InvalidPlanError` on a downstream structural fault.
4. The `except` branch calls `SessionLifecycleManager.trigger_replan` with `plan_path`, `errors`, and `original_plan_content` only.
5. `trigger_replan` applies its `title="Unknown Plan"` default and forwards it to `SessionReplanner.build_failure_report`, which sets `report.plan_title`.
6. `MarkdownReportFormatter` renders `# Execution Report: {{ report.plan_title }}`, so the sentinel reaches `report.md`.

The H1 text survives in `original_plan_content`, but no component extracts it on this branch.

### Discrepancies
- [x] Expected the report title to match the H1, observed `Unknown Plan` (Resolved: the structural branch omits `title`, so the lifecycle manager sentinel lands in `report.plan_title`).
- [x] Two fallback literals exist (Resolved: `"Untitled Plan"` is the formatter default; `"Unknown Plan"` is the `trigger_replan` default).
- [x] A stored `report.md` matched the literal (Resolved: the match quotes the bug text inside an embedded user request, not a rendered title).
- [x] `_parse_and_handle_structural_errors` appeared to be a live structural call site (Resolved: no references exist outside its definition).
- [x] The fix risked breaking a shared contract (Resolved: the audit confirmed four `trigger_replan` callers remain signature-compatible and the full suite stayed green).

### Investigation History
1. Searched the source for the literal; found one producer, the `title` default on `SessionLifecycleManager.trigger_replan`.
2. Read the report template and formatter; confirmed the header renders `report.plan_title` and the formatter fallback is `"Untitled Plan"`.
3. Traced `trigger_replan` into `SessionReplanner.build_failure_report`; confirmed the title argument becomes `report.plan_title`.
4. Read the orchestrator call sites; confirmed the logical validation path forwards `plan.title` and the structural paths do not.
5. Searched `.teddy/sessions` for a real failing report; found only quoted bug text, so the bug needs a purpose-built MRE.
6. Confirmed `_parse_and_handle_structural_errors` is dead code and `_prepare_plan_parsing` is the reachable structural branch.
7. Read the parser; confirmed the H1 is extracted into `Plan.title` and downstream structural faults raise `InvalidPlanError`.
8. Ran `git log -S "Unknown Plan"`; identified the commits that introduced and touched the sentinel.
9. Executed the minimal reproducible example at [01-unknown-plan-report-title-mre.py](/spikes/debug/unknown-plan-report/01-unknown-plan-report-title-mre.py) against unmodified production code; observed `plan_title='Unknown Plan'` and a `report.md` header of `# Execution Report: Unknown Plan`, which confirmed the Causal Model at runtime.
10. Copied the faulty module to [replica_session_orchestrator.py](/spikes/debug/unknown-plan-report/replica_session_orchestrator.py) and patched it with an H1 extractor plus conditional title forwarding; reran the MRE against the replica; observed `plan_title='A Perfectly Valid Title'` and the matching header, which proved the fix in isolation.
11. Applied the identical patch to `src/teddy_executor/core/services/session_orchestrator.py` and appended a regression test to `tests/suites/unit/core/services/test_session_orchestrator.py`; the targeted module passed 26 tests and the full suite passed 1984 tests with 5 skips.
12. Ran the impact audit; confirmed one helper definition with one call site and four signature-compatible `trigger_replan` callers, then cleared the ruff lint and format gates.

## Solution
### Root Cause
The parse-exception branch of `SessionOrchestrator._prepare_plan_parsing` called `SessionLifecycleManager.trigger_replan` without a `title`, so the lifecycle manager applied its `"Unknown Plan"` default and the failure report rendered that sentinel instead of the plan H1. The H1 text was present in `original_plan_content`, but no component extracted it on this branch. The fix was proven in the sandbox replica, then applied directly to production. A module-level `_extract_plan_title` helper now reads the first Level 1 heading from the raw content, and the parse-exception branch forwards it through conditional `title` insertion while leaving the `"Unknown Plan"` sentinel as the single source of truth in the lifecycle manager. The regression test drives the public `execute` path and asserts the forwarded title.

### Affected Components
- `SessionOrchestrator._prepare_plan_parsing`: now extracts the H1 and forwards it on the parse-exception branch (changed in [session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py)).
- `SessionLifecycleManager.trigger_replan`: keeps the `"Unknown Plan"` default as the single source of truth; no change required.
- `SessionReplanner.build_failure_report`: consumes the forwarded title into `report.plan_title`; no change required.
- `MarkdownReportFormatter`: renders the forwarded title into `report.md`; no change required.
- `tests/suites/unit/core/services/test_session_orchestrator.py`: carries the new regression test.
