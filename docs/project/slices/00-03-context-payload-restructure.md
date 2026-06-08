# Slice: Restructure Context Payload Format
- **Status:** In Progress
- **Type:** Refactor
- **Milestone:** N/A (Ad-hoc)
- **Specs:** [docs/project/specs/context-payload-format.md](/docs/project/specs/context-payload-format.md)
- **Component Docs:** [docs/project/specs/context-payload-format.md](/docs/project/specs/context-payload-format.md)

## Business Goal
Restructure the `context-payload-format.md` specification to (1) remove numbering prefixes from all section titles for cleaner formatting, and (2) move the "Session History" section to immediately after "System Information" for a more logical flow.

## Scenarios
N/A — This is a documentation refactoring task, not a feature with user-facing scenarios.

## Edge Cases
- **Cross-References**: If other documents reference the numbered section titles (e.g., `## 4. Resource Contents`), those references must be updated to match the new unnumbered titles.
- **Internal References**: Within the spec itself, ensure all internal cross-references are updated to use the new unnumbered titles.

## Deliverables
- [ ] **Contract** - Define the new section ordering and title format in the implementation plan.
- [ ] **Logic** - Remove numbering prefixes from all section titles in `context-payload-format.md`.
- [ ] **Logic** - Move "Session History" section to after "System Information".
- [ ] **Cleanup** - Update cross-references to numbered titles in other documentation files.

## Implementation Notes
[To be filled during implementation]

## Implementation Plan
### Summary of Changes
1. Modify `docs/project/specs/context-payload-format.md`:
   - Change `## 1. System Information` → `## System Information`
   - Change `## 2. Git Status` → `## Git Status`
   - Change `## 3. Project Structure` → `## Project Structure`
   - Change `## 4. Resource Contents` → `## Resource Contents`
   - Change `## 5. Session History` → `## Session History`
   - Move the entire "## Session History" subsection block (including all its content) to immediately after "## System Information"

2. Search for and update any cross-references to numbered titles in other documentation files.

### Key Constraint
Each deliverable must be a single, atomic change. No `CREATE` and `EDIT` of the same file in one plan.
