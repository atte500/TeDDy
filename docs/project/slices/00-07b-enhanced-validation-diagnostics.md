# Slice: Enhanced Validation Diagnostics
- **Status:** Planned
- **Milestone:** [docs/project/milestones/09-interactive-session-and-config.md](/docs/project/milestones/09-interactive-session-and-config.md)
- **Specs:** [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md)

## 1. Business Goal
To improve the reliability of the AI's automated self-correction loop by providing significantly more detailed, contextual, and actionable feedback when a plan fails pre-flight validation checks. This enhancement will reduce failed runs and improve the AI's ability to recover from its own errors.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Structural Validation Error [✓]
**Given** a plan with top-level structural errors (e.g., a missing `## Rationale` section)
**When** the plan is validated
**Then** the `InvalidPlanError` message must display a flat list of all top-level AST nodes.
**And** each node must be prefixed with its validation status (`[✓]`, `[✗]`, or `[ ]`) and its index (`[000]`).
**And** each failing node must include a parenthetical `(Error: ...)` explaining the specific reason for the failure.
**And** trailing nodes after the first failure must be marked as unvalidated (`[ ]`).
**And** the output must exactly match the format demonstrated in the reference spike for structural errors.

#### Deliverables
- [✓] Update `format_structural_mismatch_msg` in `src/teddy_executor/core/services/parser_infrastructure.py` to produce the new error format.
- [✓] Ensure existing unit tests for structural errors are updated to assert against the new, more detailed output format.

#### Implementation Notes
- Refactored `format_structural_mismatch_msg` to support rich diagnostic formatting (status prefixes, indices, and parenthetical errors).
- Implemented `failure_cutoff_idx` logic to mark nodes following a failure as unvalidated `[ ]`.
- Updated `MarkdownPlanParser` and action strategies to propagate `offending_node` context to improve surgical reporting.
- Simplified `MarkdownPlanParser.parse` catch-all to avoid redundant error messaging.
- Removed dead code `MISMATCH_INDICATOR` and aligned the entire test suite (unit, integration, acceptance) with the new formatting.
- Improved `Code Block` naming to include backtick counts for better debuggability.

---

### Scenario 2: Logical Validation Error
**Given** a plan that is structurally correct but contains a logical error (e.g., an `EDIT` action on a non-existent file)
**When** the plan is validated by `PlanValidator`
**Then** the resulting `InvalidPlanError` must contain a detailed summary of the logical error.
**And** the error message must also include a "hybrid" visualization of the plan's AST.
**And** the AST visualization must be flat by default.
**And** the specific AST node that caused the logical failure must be marked with `[✗]`.
**And** all direct children of the failing node must be indented to provide localized context.
**And** all other nodes (siblings, cousins, etc.) must remain at the top level of indentation.
**And** the output must exactly match the format demonstrated in the reference spike for logical errors.

#### Deliverables
- [ ] Create a new service/utility responsible for generating the AST visualization for any given plan.
- [ ] Update the `PlanValidator` service in `src/teddy_executor/core/services/plan_validator.py` to catch specific validation exceptions (e.g., `FileNotFoundError`).
- [ ] The `PlanValidator` must use the new AST visualization utility to generate the hybrid error report when a logical validation failure occurs.
- [ ] The `PlanValidator` must raise a new `InvalidPlanError` containing this richly formatted message.
- [ ] Add new integration tests in `tests/integration/core/services/test_plan_validator_integration.py` to verify the complete output for various logical failures (`EDIT` on non-existent file, `CREATE` with overwrite conflict, etc.).

## 3. Architectural Changes
- A new, reusable service/utility will be introduced to traverse a parsed plan's AST and generate the formatted, indexed, and recursively decorated string output.
- `PlanValidator` will be refactored to use this new utility to generate error messages for all logical validation failures, ensuring a consistent UX.
