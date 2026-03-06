# Slice 09-04: Core Session & Context Engine
- **Status:** [✅] Completed

## 1. Business Goal

To transform TeDDy from a stateless CLI tool into a stateful, local-first session manager. This slice implements the "backbone" of the interactive workflow, allowing users to create sessions, generate turn-based context payloads, and execute plans that automatically transition to the next turn.

-   **Source Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/09-interactive-session-and-config.md)

## Preliminary Refactoring

To support the stateful session workflow, we must first generalize the context-gathering infrastructure.

1.  **Refactor `FileSystemManager` Port:**
    -   **Deprecate:** `get_context_paths()`. It is too specific (hardcoded to `.teddy/*.context`).
    -   **Add:** `resolve_paths_from_files(file_paths: Sequence[str]) -> List[str]`. This method will read a list of `.context` files and return a deduplicated list of the paths they contain.
2.  **Generalize `ContextService`:**
    -   Update `get_context()` to accept an optional `context_files: Sequence[str]`.
    -   If provided, it uses `resolve_paths_from_files` on those specific files.
    -   If not provided (Legacy/Manual mode), it defaults to looking for all `.context` files in the `.teddy/` root.

## 2. Interaction Sequence

1.  **Initialization:** User runs `teddy new <name>`, creating the `.teddy/sessions/<name>/01/` directory and seeding `session.context`.
2.  **Context Generation:** User runs `teddy context` (or `teddy plan` which calls it implicitly). The system aggregates context from `session.context` and `01/turn.context` to generate `01/input.md`.
3.  **Execution & Transition:** User runs `teddy execute 01/plan.md`. The system:
    -   Executes the plan actions.
    -   Calculates the next turn's state (adding/removing paths from `turn.context` based on `READ`/`PRUNE`).
    -   Creates `02/` with updated metadata and context.
    -   Generates `01/report.md`.

## 3. Acceptance Criteria (Scenarios)

### Scenario: `teddy new` bootstraps a session
- **Given** no existing session named "feat-x".
- **When** I run `teddy new feat-x`.
- **Then** a directory `.teddy/sessions/feat-x/01/` MUST be created.
- **And** `.teddy/sessions/feat-x/session.context` MUST exist and contain the content of `.teddy/init.context`.
- **And** `01/system_prompt.xml` MUST be populated with the default agent prompt.
- **And** `01/meta.yaml` MUST contain a valid `turn_id` and `creation_timestamp`.

### Scenario: `teddy context` aggregates cascading context
- **Given** a session with "file_a.py" in `session.context` and "file_b.py" in `01/turn.context`.
- **When** I run `teddy context` inside the `01/` directory.
- **Then** the generated `input.md` MUST contain the contents of both "file_a.py" and "file_b.py".
- **And** "file_b.py" MUST be listed under the "Turn" section of the Context Summary.

### Scenario: `teddy execute` triggers turn transition
- **Given** a plan in `01/plan.md` containing a `READ` action for "new_file.py".
- **When** I run `teddy execute 01/plan.md`.
- **Then** a directory `02/` MUST be created.
- **And** `02/turn.context` MUST contain "new_file.py" and "01/report.md".
- **And** `02/meta.yaml` MUST have `parent_turn_id` pointing to the ID of turn 01.

## 4. Architectural Changes

The core of the interactive workflow is managed by three new services and a specialized orchestrator.

-   **Core Domain:**
    -   `SessionLedger`: A new domain entity representing the `meta.yaml` data.
-   **Ports Layer:**
    -   `IPlanningUseCase`: Inbound port for generating a plan from a user message.
    -   `ISessionManager`: Outbound port for managing turn directories and metadata persistence.
-   **Services Layer:**
    -   [PlanningService](/docs/architecture/core/services/planning_service.md): Orchestrates context gathering and LLM communication.
    -   `SessionService`: Implements the `ISessionManager` and directory lifecycle logic.
    -   [ContextService](/docs/architecture/core/services/context_service.md): Refactored to support parameterized context sources.
    -   `SessionOrchestrator`: A wrapper service implementing the "Turn Transition Algorithm" around the base `ExecutionOrchestrator`.

## 5. Deliverables

### 1. Infrastructure Refactoring
- [x] **Refactored `FileSystemManager`**: Generalized context path resolution.
- [x] **Refactored `ContextService`**: Parameterized to support session-specific context files.

### 2. Session Management
- [x] **`SessionService`**: Implementation of directory creation, `meta.yaml` management, and turn-id generation.
- [x] **`SessionOrchestrator`**: Implementation of the Turn Transition Algorithm (T_current -> T_next).

### 3. Planning & LLM Integration
- [x] **`PlanningService`**: Implementation of the plan generation loop (Context -> LLM -> plan.md).
- [x] **CLI Implementation**: Update the `typer` app in `__main__.py` to include `new`, `plan`, and `resume` (which utilizes the `SessionOrchestrator`).
- [x] **Context Hint Injection**: Implement logic to append "Session Start" and "Alignment" hints to user messages during planning as per specification.

### 4. Verification
- [x] **Integration Tests**: Verifying cascading context (init -> session -> turn).
- [x] **Acceptance Tests**: Verifying full turn-to-turn transitions including `READ` action side-effects.

## Implementation Summary

I have transformed TeDDy from a stateless CLI tool into a stateful, local-first session manager.

### Key Changes
- **Session Architecture:** Introduced `SessionService` and `SessionOrchestrator` to manage the lifecycle of session directories and automate turn transitions.
- **Context Engine:** Generalised `FileSystemManager` and `ContextService` to support arbitrary context sources, enabling the cascading context model (`init` -> `session` -> `turn`).
- **LLM Integration:** Implemented `PlanningService` to orchestrate plan generation with implicit context gathering and Turn 1 alignment hints.
- **CLI Evolution:** Decomposed `__main__.py` into a modular `session_cli_handlers.py` and implemented the new `new`, `context`, `plan`, and state-aware `resume` commands.
- **Quality Gates:** Rebalanced the Test Pyramid by moving system-wiring tests (Lazy Loading) to the integration layer to ensure compliance with architectural standards.

### [NEW] Reminders for next cycle
- [NEW]: The `resume` command currently uses a simple `input()` prompt for messages; this should be upgraded to use the `textual`-based TUI in the next slice.
- [NEW]: `PlanningService` hardcodes `gpt-4o`; this should be moved to the `ConfigService` in the next refinement.
