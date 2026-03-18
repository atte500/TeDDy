# Slice 09-05: Plan Validation & Self-Correction
- **Status:** [✓] Completed

## 1. Business Goal

To enhance the reliability of the TeDDy workflow by catching common errors before execution and enabling the AI to self-correct. This slice integrates the `PlanValidator` into the execution flow and implements the "Automated Re-plan Loop" for stateful sessions.

-   **Source Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 2. Interaction Sequence

### Successful Execution (Validation Passes)
1.  **Trigger:** User runs `teddy execute 01/plan.md`.
2.  **Validation:** `SessionOrchestrator` calls `PlanValidator.validate(plan)`.
3.  **Result:** No errors found.
4.  **Proceed:** Orchestrator proceeds to Tier 1 Approval/Execution.

### Automated Re-plan Loop (Validation Fails)
1.  **Trigger:** User runs `teddy execute 01/plan.md`.
2.  **Validation:** `SessionOrchestrator` calls `PlanValidator.validate(plan)`.
3.  **Result:** Validation errors found (e.g., "EDIT target not in context").
4.  **Reporting:**
    -   Orchestrator generates `01/report.md` containing the validation errors.
5.  **Transition:**
    -   Orchestrator creates `02/` directory (Turn N+1).
    -   Copies `system_prompt.xml`, `meta.yaml` (updated), etc.
    -   **Critical:** Does NOT add `01/report.md` to `02/turn.context` to keep it clean.
6.  **Auto-Plan:**
    -   Orchestrator invokes `PlanningService.plan()` for Turn 02.
    -   The user message for this plan is a structured feedback payload containing the validation errors and the original faulty plan.
7.  **Completion:** The command terminates. The user finds a new, corrected `02/plan.md` ready for execution.

## 3. Acceptance Criteria (Scenarios)

### Scenario: EDIT action must target a file in context
- **Given** a session where `turn.context` contains only `README.md`.
- **And** a plan in `01/plan.md` containing an `EDIT` action for `src/main.py`.
- **When** I run `teddy execute 01/plan.md`.
- **Then** validation MUST fail with an error: "`src/main.py` is not in the current turn context".
- **And** the automated re-plan loop MUST be triggered.

### Scenario: PRUNE action must target a file in context
- **Given** a session where `turn.context` contains `README.md`.
- **And** a plan in `01/plan.md` containing a `PRUNE` action for `docs/ARCH.md`.
- **When** I run `teddy execute 01/plan.md`.
- **Then** validation MUST fail with an error: "`docs/ARCH.md` is not in the current turn context".

### Scenario: READ action must NOT target a file already in context
- **Given** a session where `session.context` contains `README.md`.
- **And** `turn.context` contains `src/main.py`.
- **And** a plan in `01/plan.md` containing a `READ` action for `README.md`.
- **When** I run `teddy execute 01/plan.md`.
- **Then** validation MUST fail with an error: "`README.md` is already in context".

### Scenario: Automated Re-plan triggers on structure error
- **Given** a plan in `01/plan.md` with a malformed metadata block.
- **When** I run `teddy execute 01/plan.md`.
- **Then** a `report.md` MUST be generated in `01/`.
- **And** a new turn `02/` MUST be created.
- **And** `02/plan.md` MUST be generated automatically by the AI.

## 4. Architectural Changes

### Core Logic
- **`PlanValidator` ([Contract](/docs/architecture/core/ports/inbound/plan_validator.md))**: Updated to support context-aware validation (READ, EDIT, PRUNE).
- **`SessionOrchestrator` ([Design](/docs/architecture/core/services/session_orchestrator.md))**: Implements the Automated Re-plan Loop logic.
- **`SessionService`**: Updated `transition_to_next_turn` to handle validation failures (skipping context injection for reports).
- **`PlanningService`**: Verified for re-plan support via custom user messages.

### CLI Layer
- **`execute` command**: Updated to respect the orchestrator's validation outcomes and non-zero exit codes on failure.

## 5. Deliverables

### 1. Plan Validation Enhancements
- [x] **Updated `PlanValidator`**: Implement `Session` vs `Turn` context logic.
- [x] **Updated `EDIT` Validator**: Verify target is in either context.
- [x] **Updated `PRUNE` Validator**: Verify target is ONLY in Turn context.
- [x] **Updated `READ` Validator**: Verify target is NOT in any context.

### 2. Automated Re-plan Loop
- [x] **`SessionOrchestrator` Logic**: Integrate validation check and re-plan trigger.
- [x] **`SessionService` Extension**: Add `is_validation_failure` flag to `transition_to_next_turn`.
- [x] **Feedback Payload Generator**: A utility to format validation errors for the LLM.

### 3. Verification
- [x] **Unit Tests**: Context-aware validation rules in isolation.
- [x] **Integration Tests**: Re-plan loop in `SessionOrchestrator`.
- [x] **Acceptance Tests**: Full CLI workflow for faulty plans.

## Implementation Summary

### Work Completed
- **Context-Aware Validation**: Implemented mandatory context checks for `READ` (must not be in context), `EDIT` (must be in session/turn context), and `PRUNE` (must be in turn context).
- **Automated Re-plan Loop**: Integrated the `PlanValidator` into `SessionOrchestrator`. On failure, the orchestrator generates a validation report, creates a new turn directory (excluding the failure report from context), and invokes the `PlanningService` with structured feedback to generate a corrected plan.
- **Rich Feedback Loop**: Validation reports now include the specific error messages and the contents of the files that caused the failure, providing high-clarity char-level diffs for `EDIT` mismatches.
- **Robust CLI Integration**: Updated the CLI `execute` command to support pre-flight validation in both standalone (manual) and stateful (session) modes.

### Significant Refactorings
- **Validator Strategy Pattern**: Refactored `PlanValidator` to use a registry of action-specific validators, facilitating easier extension for new action types.
- **BaseActionValidator Hierarchy**: Introduced a `BaseActionValidator` class and a centralized `is_path_in_context` helper. This resolved code duplication across `CREATE`, `EDIT`, `READ`, and `PRUNE` validators while ensuring consistent path normalization and safety checks.
- **Service Orchestration**: Decoupled validation logic from core execution by implementing it as a decorator-style gate in `SessionOrchestrator`.

### Lessons Learned
- **Privacy by Design**: Enforced rule ordering in `EDIT` validation to check context *before* existence, preventing potential information leakage about the host filesystem.
- **Stateless/Stateful Alignment**: Maintained strict separation between manual and session modes, ensuring "secure by default" validation while allowing flexible manual overrides.

## 6. User Showcase

### Manual Verification of Re-plan Loop
1.  Initialize a new session: `teddy new test-validation`.
2.  Manually create a faulty plan in `.teddy/sessions/test-validation/01/plan.md` (e.g., an `EDIT` action with a `FIND` block that doesn't exist).
3.  Run the execution: `teddy execute .teddy/sessions/test-validation/01/plan.md`.
4.  **Verify:**
    -   Command outputs that validation failed.
    -   Check `.teddy/sessions/test-validation/01/report.md` for errors.
    -   Check for the existence of `.teddy/sessions/test-validation/02/plan.md`.
    -   Inspect `.teddy/sessions/test-validation/02/plan.md` to see if the AI addressed the specific error.
