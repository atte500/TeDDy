# Slice: 02-10-Preserve User-Message Turns
- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Prototype:** [spikes/prototypes/10-preserve-user-message-turns.py](/spikes/prototypes/10-preserve-user-message-turns.py)
- **Component Docs:** [docs/architecture/core/services/session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md)

## Business Goal
Protect action turns where the user provided an additional message during the review phase from being pruned by the automatic session pruning logic. This ensures user contributions are preserved in the session context for future turns.

## Scenarios
> As a user, I want action turns where I provided a message during review (via TUI 'm' key or reply) to be spared from auto-pruning, so that my instructions and context are not lost.
```gherkin
Given a session with auto-pruning enabled
And the active turn has a plan with actions (not a ## Message turn)
And the user provided an additional message during review
When the pruning service evaluates this turn
Then the turn should be spared from pruning
And its files should remain selected in the project context
```

> As a user, I want pure message turns (## Message plans) to continue being spared from auto-pruning, so that the existing behavior is preserved.
```gherkin
Given a session with auto-pruning enabled
And a turn has a plan containing a ## Message section (message turn)
And the report shows Overall Status: SUCCESS
When the pruning service evaluates this turn
Then the turn should be spared from pruning
And its files should remain selected in the project context
```

## Edge Cases
- **Missing Report File**: If a turn has a plan but no report.md (e.g., execution was aborted), the service should not crash and should not attempt to read a missing file.
- **Empty User Request**: If the user_request metadata line is present but empty, the turn should not be spared (empty message is not a meaningful contribution).
- **Concurrent User Request and User Message**: If a turn contains both a `## Message` plan and a `user_request` metadata entry, it should be spared (already covered by existing message turn sparing).
- **Multiple Pruning Heuristics**: A turn spared by this rule must be exempted from ALL pruning heuristics (retention limit, global budget, non-green recovery, validation failure) to be consistent with existing message turn sparing.

## Deliverables
- [x] **Harness** - Unit tests for `_check_report_has_user_request` helper (positive: report with user_request; negative: report without; edge: missing file, empty value).
- [x] **Harness** - Unit tests for spared turn integration (turns with user_request are not pruned by retention limit or global budget).
- [ ] **Logic** - Implement `_check_report_has_user_request(path: str) -> bool` in `SessionPruningService` to detect `- **User Request:**` pattern in report files.
- [ ] **Logic** - Extend `_update_turn_metadata_from_item` to collect turn IDs where the report has a user request and add them to the spared set.
- [ ] **Wiring** - Integration test verifying full pruning flow: session with user-request turn is not pruned.
- [ ] **Refactor** - Rename `successful_messages` variable (and all related parameter names via the call chain: `_collect_turn_metadata`, `_identify_turns_to_prune`, `_apply_retention_limit`, `_apply_global_budget`) to `spared_turns` to reflect the broader sparing logic. Single-file change in `session_pruning_service.py`. No shared seam impact — 6 occurrences all within the same class.

## Implementation Notes

### Deliverable 2: Harness — Spared Turn Integration Tests
- **Test File:** [`tests/suites/unit/core/services/test_session_pruning_preserve_user_requests.py`](/tests/suites/unit/core/services/test_session_pruning_preserve_user_requests.py)
- **Status:** Completed (2 integration tests, both passing)
- **Test Coverage:**
  1. `test_user_request_turn_not_pruned_by_retention_limit`: Creates 5 turns with varying retention limits — verifies that turns with user_request metadata (turn 01) are NOT pruned even when below the retention threshold.
  2. `test_user_request_turn_not_pruned_by_global_budget`: Creates turns with large token counts — verifies that turns with user_request metadata are NOT pruned by the global budget heuristic.
- **Key Findings:**
  - The production code already had user_request sparing logic fully wired in `_update_turn_metadata_from_item` (the `# NEW: Sparing via user_request metadata` code block was present at the time the tests were written). The Harness tests validate existing behavior rather than driving new implementation.
  - The `ContextItem` import from `teddy_executor.core.domain.models.project_context` is required for type hints in the test file.
  - The `_collect_turn_metadata` private method is accessed directly in the tests, which is acceptable for unit testing within the same package.
- **No Refactoring Needed:** Test file uses constructor injection, register_mock for config service, and `create_autospec` for the file system manager. No global `mock.patch`, no magic numbers, no shadow logic.
- **Integration:** Full suite passes with 803 passed, 3 skipped — no regressions.

### Deliverable 1: Harness — Unit tests for `_check_report_has_user_request`
- **Test File:** [`tests/suites/unit/core/services/test_session_pruning_preserve_user_requests.py`](/tests/suites/unit/core/services/test_session_pruning_preserve_user_requests.py)
- **Status:** Completed (7 tests, all passing)
- **Test Coverage:**
  1. `test_detects_user_request_header_in_report`: Positive — detects `- **User Request:**` with value → True
  2. `test_detects_user_request_header_without_content`: Positive — detects empty `- **User Request:**` → True
  3. `test_returns_false_when_no_user_request`: Negative — report without user_request → False
  4. `test_returns_false_for_missing_report_file`: Edge — missing file → False (no crash)
  5. `test_returns_false_for_unreadable_report_file`: Edge — read_file raises OSError → False
  6. `test_matches_user_request_header_inside_code_block`: Positive — pattern matches anywhere on its own line (by design, the header always indicates user interaction regardless of code block context) → True
  7. `test_returns_false_when_read_file_returns_empty_string`: Edge — empty file → False
- **Key Design Decisions:**
  - Uses `create_autospec` (bound mocks) for both `IConfigService` and `IFileSystemManager` to prevent signature drift
  - The regex `r"^- \*\*User Request:\*\*"` with `re.MULTILINE` correctly matches the header on its own line, even when inside a code block — the presence of the key itself indicates user interaction
  - Empty user_request value (key present but no content) still spares the turn, matching the Implementation Plan's edge case specification
  - The production code already had `_check_report_has_user_request` implemented (Logic deliverable was pre-satisfied), so this Harness deliverable validates existing behavior
- **Production Code:** `SessionPruningService._check_report_has_user_request` at [`src/teddy_executor/core/services/session_pruning_service.py`](/src/teddy_executor/core/services/session_pruning_service.py)
- **No Refactoring Needed:** Test file is clean — uses constructor injection, no global `mock.patch`, no magic numbers, no shadow logic
- **Integration:** Full suite passes with 788 passed, 3 skipped — no regressions

### Turn 1: Exploration
- Read `SessionPruningService`, `ExecutionReport`, `SessionOrchestrator`, `ExecutionReportAssembler`, and specs.
- Current sparing logic only preserves turns with `## Message` plans (via `_check_plan_is_message` + `_check_report_is_success`).
- Gap: Action turns with `user_request` in report metadata are not spared.
- No port or domain model changes needed — only internal refactoring of `SessionPruningService`.

### Turn 2: Alignment
- Approved approach: Add `_check_report_has_user_request` check, extend `_update_turn_metadata_from_item` to collect user-request turn IDs, add them to spared set.
- Identified debt: `successful_messages` variable name is semantically misleading after this change; rename to `spared_turns` in cleanup.

## Implementation Plan

### Summary of Changes
No new ports or domain models needed. All changes are confined to a single file: `SessionPruningService` in [`src/teddy_executor/core/services/session_pruning_service.py`](/src/teddy_executor/core/services/session_pruning_service.py).

### Delta Analysis (Prototype-Validated)

#### 1. New Method: `_check_report_has_user_request(self, path: str) -> bool`
- **What:** Reads a report file and checks for the `- **User Request:**` pattern using regex.
- **Regex pattern (prototype-validated):** `r"^- \*\*User Request:\*\*"` with `re.MULTILINE`
- **Behavior:** Returns `True` if the pattern is found, `False` if the file is missing, unreadable, or the pattern is absent. No caching concern — `_safe_read` already handles caching within a single `prune()` call.
- **Edge case: empty value**: If the line is `- **User Request:**` with no content, the regex still matches (the line exists). This correctly spares turns where the user_request metadata was written with an empty value — the presence of the key itself indicates user interaction occurred.

#### 2. Modify `_update_turn_metadata_from_item`
- **Location:** Add a new metadata collection path after the existing Heuristic 4 (validation failure) and Heuristic 3 (non-green) checks, alongside the existing message-turn sparing.
- **Logic (prototype-validated):**
  ```python
  # NEW: Sparing via user_request metadata
  if posix_path.endswith("report.md"):
      if self._check_report_has_user_request(item.path):
          state["spared"].add(turn_id)
  ```
- **Key design decision:** The user_request check is done on the `report.md` file (not the `plan.md` file) because the `user_request` metadata is written to the report during execution. This is consistent with the existing message-turn sparing which checks the plan for `## Message` and the report for `SUCCESS`.
- **Why NOT on plan.md:** The `plan.metadata["user_request"]` is captured during execution in `execution_orchestrator.py` and `session_orchestrator.py`, then rendered into the report via `execution_report.md.j2`. By the time pruning runs, the report is the canonical source of truth.

#### 3. Rename `successful_messages` → `spared_turns`
- **Scope:** Single file (`session_pruning_service.py`), 6 occurrences:
  1. Line 125: variable assignment in `_identify_turns_to_prune`
  2. Line 137: `for tid in successful_messages` loop
  3. Line 140: return statement
  4. Line 152: local variable initialization in `_collect_turn_metadata`
  5. Line 174: dictionary value assignment
  6. Line 183: return statement
- **Renaming also affects:** The `spared_turns` set flows through `_apply_retention_limit` and `_apply_global_budget` parameter names. Both methods already use parameter name `spared_turns` in the production code (verified by reading source). The return tuple from `_collect_turn_metadata` needs updating from `successful_messages` to `spared_turns`.
- **No shared seam impact:** No other files import or reference `successful_messages`. The rename is purely internal to `SessionPruningService`.

### Existing `user_request` Infrastructure (Prototype-Discovered)
The prototype revealed that extensive infrastructure for `user_request` already exists across the codebase. This confirms the approach is well-supported:

| Component | File | How `user_request` is used |
|---|---|---|
| **ExecutionReport** | `execution_report.py:58` | `user_request: str \| None = None` field |
| **ExecutionReportAssembler** | `execution_report_assembler.py:38` | Reads from plan metadata |
| **ExecutionOrchestrator** | `execution_orchestrator.py:106,203` | Captures from user message and resolves |
| **SessionOrchestrator** | `session_orchestrator.py:203-208` | Updates report/plan metadata |
| **SessionService** | `session_service.py:311-312` | Carries over in metadata across turns |
| **Report Template** | `execution_report.md.j2:128-133` | Renders `- **User Request:**` header in report output |
| **TUI App** | `textual_plan_reviewer_app.py:367` | Sets metadata from TUI input |
| **TUI Previews** | `textual_plan_reviewer_previews.py:222` | Reads for display |

### Report Format (Template-Validated)
The Jinja2 template (`execution_report.md.j2`) renders the user_request as:
```markdown
{% if report.user_request %}
- **User Request:**
{{ report.user_request | fence }}text
{{ report.user_request }}
{{ report.user_request | fence }}
{% endif %}
```
This produces a header line `- **User Request:**` followed by the user's message in a fenced code block. The prototype's regex `r"^- \*\*User Request:\*\*"` correctly matches this header on its own line, regardless of whether the content block follows.

### Prototype-Validated Scenarios
The prototype at [`spikes/prototypes/10-preserve-user-message-turns.py`](/spikes/prototypes/10-preserve-user-message-turns.py) empirically verified:

| Scenario | Expected | Result |
|---|---|---|
| Turn with `user_request` — spared from retention limit | Spared ✓ | ✓ |
| Turn with `user_request` — spared from global budget | Spared ✓ | ✓ |
| Pure `## Message` turn — spared (regression check) | Spared ✓ | ✓ |
| Normal turn without sparing — pruned | Pruned ✓ | ✓ |

### Impact Audit
- **Shared Seams:** None. `SessionPruningService` has no consumers beyond the `SessionOrchestrator`/`SessionPlanner` context preparation flow (internal to the session boundary).
- **Test File:** [`tests/suites/unit/core/services/test_session_pruning_service_refinement.py`](/tests/suites/unit/core/services/test_session_pruning_service_refinement.py) exists. The developer should add the new unit tests there or create a dedicated [`test_session_pruning_service.py`](/tests/suites/unit/core/services/test_session_pruning_service.py) file.
- **DI Alignment:** The `SessionPruningService` constructor takes `IConfigService` and `IFileSystemManager` — both are already injected. No new dependencies needed.

### Flow Diagram
```
flowchart TD
    A[SessionPruningService.prune] --> B[_identify_turns_to_prune]
    B --> C[_collect_turn_metadata]
    C --> D[_update_turn_metadata_from_item]
    D --> E{report has user_request?}
    E -->|Yes| F[Add turn ID to spared_turns set]
    E -->|No| G{plan is ## Message?}
    G -->|Yes + SUCCESS| F
    G -->|No| H[Continue normal pruning]
    F --> I[Exempt spared turns from all heuristics]
    I --> J[Return pruned context]
```
