# Slice: Restructure Context Payload Format
- **Status:** Completed
- **Type:** Refactor
- **Milestone:** N/A (Ad-hoc)
- **Specs:** [docs/project/specs/context-payload-format.md](/docs/project/specs/context-payload-format.md)
- **Component Docs:** [src/teddy_executor/core/services/context_service.py](/src/teddy_executor/core/services/context_service.py), [docs/project/specs/context-payload-format.md](/docs/project/specs/context-payload-format.md)

## Business Goal
Restructure the `context-payload-format.md` specification AND the corresponding `ContextService` code implementation to (1) remove numbering prefixes from all section titles for cleaner formatting, and (2) move the "Session History" section to immediately after "System Information" for a more logical flow. The code that generates `input.md` must produce the new structure.

## Scenarios
N/A — This is a documentation and code refactoring task, not a feature with user-facing scenarios.

## Edge Cases
- **Code-Spec Sync**: The `ContextService` code and the spec document must be updated together to stay in sync.
- **Cross-References**: If other documents reference the section titles (e.g., `## Resource Contents`), those references should use the unnumbered format.
- **Internal References**: Within the spec itself, ensure all internal cross-references are updated to use the new unnumbered titles.
- **Test Assertions**: Unit and acceptance tests assert on numbered titles and must be updated last (Cleanup).

## Deliverables
- [x] **Logic** - Update `ContextService` code: remove numbering from section title strings, and move "Session History" section assembly to after "System Information".
- [▶] **Logic** - Update spec document: remove numbering prefixes and reorder "Session History" after "System Information".
- [ ] ~~Cleanup - Update test assertions in `test_context_service.py` and `test_context_command_refactor.py` that reference old numbered titles.~~ _(Already completed inline in Deliverable 1)_
- [x] **Cleanup** - Update cross-references to numbered titles in other documentation files.

## Implementation Notes
- **Deliverable 1 (Code Changes)**: Successfully completed. Four edits applied to `context_service.py`:
  1. `_format_header()`: `## System Information` — removed numbering prefix
  2. `_format_workspace_contents()`: `## Resource Contents` — removed numbering prefix
  3. `_format_session_history()`: `## Session History` — removed numbering prefix
  4. `_format_content()`: Restructured to prepend Session History before Git Status/Project Structure/Resource Contents (placing it immediately after the header's System Information section)
- **Test Assertions (Absorbed into Deliverable 1)**: All test assertions referencing numbered titles were updated inline during the Implementation phase to maintain Green-to-Green state. Deliverable 3 (Cleanup - test assertions) is now redundant.
- **Key Learning**: When updating section titles that appear in both code and tests, update tests first (Red), then code (Green), then run full suite to catch remaining references.
- **All 820+ tests pass** with unnumbered titles and reordered sections.

## Implementation Plan
### Summary of Changes

#### 1. Code Changes (`src/teddy_executor/core/services/context_service.py`)
- `_format_header()` (line 273): Changed `## 1. System Information` → `## System Information`
- `_format_content()` (line 298): Reordered section assembly so "Session History" section is prepended first in content (immediately after the header's "System Information"), ahead of "Git Status", "Project Structure", and "Resource Contents"
- `_format_workspace_contents()` (line 336): Changed `## 4. Resource Contents` → `## Resource Contents`
- `_format_session_history()` (line 413): Changed `## 5. Session History` → `## Session History`

#### 2. Spec Changes (`docs/project/specs/context-payload-format.md`)
- Change all `## N. Title` to `## Title` for sections 1-5
- Move the entire "## Session History" subsection block to immediately after "## System Information"

#### 3. Test Assertions (Already completed in Deliverable 1)
- `tests/suites/unit/core/services/test_context_service.py`: All numbered title assertions updated
- `tests/suites/acceptance/test_context_command_refactor.py`: All numbered title assertions updated

#### 4. Cross-References
- Search docs/ for any remaining references to numbered titles and update.

### Key Constraint
Each deliverable must be a single, atomic change. No `CREATE` and `EDIT` of the same file in one plan. Code changes MUST precede doc changes to maintain green state.
