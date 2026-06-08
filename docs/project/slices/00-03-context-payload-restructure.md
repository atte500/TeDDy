# Slice: Restructure Context Payload Format
- **Status:** In Progress
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
- **Cross-References**: If other documents reference the numbered section titles (e.g., `## 4. Resource Contents`), those references must be updated to match the new unnumbered titles.
- **Internal References**: Within the spec itself, ensure all internal cross-references are updated to use the new unnumbered titles.
- **Test Assertions**: Unit and acceptance tests assert on numbered titles and must be updated last (Cleanup).

## Deliverables
- [▶] **Logic** - Update `ContextService` code: remove numbering from section title strings, and move "Session History" section assembly to after "System Information".
- [ ] **Logic** - Update spec document: remove numbering prefixes and reorder "Session History" after "System Information".
- [ ] **Cleanup** - Update test assertions in `test_context_service.py` and `test_context_command_refactor.py` that reference old numbered titles.
- [ ] **Cleanup** - Update cross-references to numbered titles in other documentation files.

## Implementation Notes
[To be filled during implementation]

## Implementation Plan
### Summary of Changes

#### 1. Code Changes (`src/teddy_executor/core/services/context_service.py`)
- `_format_header()` (line 273): Change `## 1. System Information` → `## System Information`
- `_format_content()` (line 298): Reorder section assembly so "Session History" comes immediately after "Git Status" line and before "Project Structure"
- `_format_workspace_contents()` (line 336): Change `## 4. Resource Contents` → `## Resource Contents`
- `_format_session_history()` (line 413): Change `## 5. Session History` → `## Session History`

#### 2. Spec Changes (`docs/project/specs/context-payload-format.md`)
- Change all `## N. Title` to `## Title` for sections 1-5
- Move the entire "## Session History" subsection block to immediately after "## System Information"

#### 3. Test Assertions
- `tests/suites/unit/core/services/test_context_service.py:74`: Change `"## 1. System Information"` → `"## System Information"`
- `tests/suites/acceptance/test_context_command_refactor.py:52`: Change `"## 1. System Information"` → `"## System Information"`

#### 4. Cross-References
- Search docs/ for any remaining references to numbered titles and update.

### Key Constraint
Each deliverable must be a single, atomic change. No `CREATE` and `EDIT` of the same file in one plan. Code changes MUST precede doc changes to maintain green state.
