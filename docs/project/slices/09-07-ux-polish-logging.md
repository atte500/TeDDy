# Slice 09-07: UX Polish & Logging (Session Lifecycle)
- **Status:** Planned
- **Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/09-interactive-session-and-config.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## 1. Business Goal
To refine the user experience of the interactive session workflow by ensuring robust lifecycle transitions, providing transparent logging of AI interactions, and enabling dynamic session naming. This polish phase addresses technical debt and usability gaps discovered during the initial implementation of the session backbone.

## 2. Acceptance Criteria (Scenarios)

### Scenario: Fix Session Service FileNotFoundError (Refactoring) [✓]
- **Given** a session transition is triggered (e.g., during `execute`).
- **And** the `turn.context` file is missing in the current turn directory.
- **When** `SessionService.transition_to_next_turn` is called.
- **Then** it MUST NOT raise a `FileNotFoundError`.
- **And** it MUST treat the missing file as an empty context.

#### Deliverables
- [✓] **Robust Context Reading:** Updated `SessionService` to use a safe file reading pattern for `turn.context`.
- [✓] **Regression Test:** New integration test in `tests/integration/core/services/test_session_service.py` verifying transition with missing context.

#### Implementation Notes
- Extracted `_read_context_file` helper in `SessionService` to robustly handle reading and parsing context files (treating missing/unreadable files as empty).
- Updated `transition_to_next_turn` and `resolve_context_paths` to use the new helper.

### Scenario: Rename 'new' to 'start' and enable dynamic naming [✓]
- **Given** I am in a project directory.
- **When** I run `teddy start` without a name.
- **Then** it MUST create a session with a temporary timestamped name.
- **And** it MUST automatically rename the session directory based on the first plan's H1 title after it is generated.
- **And** it MUST flow seamlessly from initialization to planning to execution.

#### Deliverables
- [✓] **CLI Refactoring:** Renamed `teddy new` to `teddy start` in `__main__.py` and `session_cli_handlers.py`.
- [✓] **Dynamic Renaming Logic:** Implemented `ISessionManager.rename_session` in `SessionService`.
- [✓] **Orchestration Hook:** Updated `SessionOrchestrator` to trigger renaming after the first plan generation in turn `01`.
- [✓] **Acceptance Test:** New test in `tests/acceptance/test_session_management.py` verifying the `start` -> `rename` -> `execute` loop.

#### Implementation Notes
- Renamed `new` command to `start` to better reflect its "entry point" nature.
- Implemented `rename_session` in `SessionService` with collision checking.
- Updated `SessionOrchestrator` to perform "Auto-Naming": if the session name matches the ISO timestamp pattern (indicating it was created without a name), the orchestrator slugifies the first generated plan's H1 title and renames the session directory.
- Fixed a bug where `SessionOrchestrator.resume` recursion used a stale session name after a rename.

### Scenario: Robust 'resume' with path detection [✓]
- **Given** several sessions exist in `.teddy/sessions/`.
- **When** I run `teddy resume` from the project root.
- **Then** it MUST automatically pick the most recently modified session.
- **When** I run `teddy resume [path-to-folder]`.
- **Then** it MUST resolve the session regardless of whether the path points to the session root or a specific turn.

#### Deliverables
- [✓] **Auto-Detection:** Implemented latest session detection in `SessionService` (via `mtime` sorting).
- [✓] **Path Resolver:** Enhanced `handle_resume_session` in `session_cli_handlers.py` to resolve from files, turns, or session paths using `ISessionManager.resolve_session_from_path`.
- [✓] **Acceptance Test:** New test scenarios in `tests/acceptance/test_session_resume_robustness.py` verifying `resume` with various path types and auto-detection.

#### Implementation Notes
- Updated `IFileSystemManager` to include `get_mtime`.
- Updated `ISessionManager` to include `get_latest_session_name` and `resolve_session_from_path`.
- Implemented `resolve_session_from_path` using a parent-climbing algorithm looking for the `.teddy/sessions` directory structure.
- Updated the CLI `resume` command to accept an optional positional `path` argument instead of the `--session` flag, as per specification.

### Scenario: AI Transparency & Telemetry
- **Given** a planning phase is triggered.
- **When** the LLM is called.
- **Then** an `input.log` file MUST be created in the turn directory containing the exact raw payload (system + user messages) sent to the LLM.
- **And** the agent prompt MUST be saved as `[agent_name].xml` (e.g., `pathfinder.xml`) instead of the generic `system_prompt.xml`.
- **And** the CLI MUST display:
    - The model name and agent prompt being used.
    - Context usage (e.g., "Context: 15.2k / 128k tokens").
    - Cumulative session cost (e.g., "Session Cost: $0.04").

#### Deliverables
- [ ] **Adapter Extension:** Implemented `get_token_count` and `get_completion_cost` in `LiteLLMAdapter`.
- [ ] **Cost Persistence:** Updated `SessionService.transition_to_next_turn` to calculate and store `cumulative_cost` in `meta.yaml`.
- [ ] **Input Logging:** Added `input.log` generation and specific agent prompt saving in `PlanningService`.
- [ ] **Telemetry Display:** Updated `SessionOrchestrator` and CLI handlers to display model, context usage, and session cost to the user.

### Scenario: Silence the Noise
- **Given** I am running any TeDDy command that uses LiteLLM.
- **When** the command executes.
- **Then** verbose LiteLLM logs MUST be suppressed from the standard output.

#### Deliverables
- [ ] **Logging Suppression:** Explicitly disabled LiteLLM's internal verbose logging and provider list prints in the `LiteLLMAdapter`.

## 3. Architectural Changes
*This section will be populated in a later step.*
