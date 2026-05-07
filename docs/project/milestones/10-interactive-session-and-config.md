# Milestone 10: Interactive Session Workflow & LLM Integration

- **Status:** Planned

## 1. Goal (The "Why")

This milestone represents a major strategic evolution for TeDDy. It combines establishing core, decoupled services for configuration and LLM interaction with the implementation of a seamless, local-first, CLI-driven interactive session workflow. The goal is to realize the "Obsidian for AI coding" philosophy by managing stateful, multi-turn AI collaboration directly on the filesystem.

-   **Referenced Specifications:**
    -   [Foundational Restructuring](../specs/foundational-restructuring.md)
    -   [Interactive Session Workflow](../specs/interactive-session-workflow.md)
    -   [Context Payload Format](../specs/context-payload-format.md)
    -   [Report Format](../specs/report-format.md)

## 2. Proposed Solution (The "What")

1.  **Config, Security & LLM Foundation:**
    -   A singleton `ConfigService` reading from `.teddy/config.yaml` (which will contain sensitive LLM API keys).
    -   **Comprehensive Security Gates:**
        -   **Secret Scanning:** Integration of `detect-secrets` or `trufflehog` to prevent API key leaks.
        -   **Code Security Scanning:** Integration of `bandit` to identify insecure coding patterns.
        -   **Dependency Auditing:** Integration of `pip-audit` to detect vulnerabilities in third-party libraries.
    -   An `ILlmClient` port with a `LiteLLMAdapter` implementation using the `litellm` library.
2.  **Session Manager:** A service handling all stateful filesystem interactions (creating turn directories, managing session artifacts).
3.  **Context-Centric Workflow:** An implicitly generated `input.md` file serving as the AI's complete worldview for each turn.
4.  **Refactored CLI:** New session-aware commands (`new`, `resume`, `plan`, `execute`, `context`), with a smart `resume` orchestrator.
5.  **Interactive TUI:** A multi-layered approval workflow using `textual`, featuring "Context-Aware Editing" to preview/modify AI actions inline.
6.  **Plan Validation & Auto Re-planning:** Comprehensive pre-flight validation catching errors (e.g., `FIND` blocks) and automatically triggering a self-correction AI loop.
7.  **Agent Collaboration & Ledger:** Supporting multi-agent sub-routines via `INVOKE`/`RETURN`, tracked by a `meta.yaml` ledger and a comprehensive `session-log.md`.

## 3. Implementation Guidelines (The "How")

-   **Security First:** Before implementing the `ConfigService`, add a secret scanner to the pre-commit hooks and verify it catches mock API keys in test configurations.
-   **Integration:** The `LiteLLMAdapter` and `ConfigService` will be instantiated in the `main.py` composition root.
-   **CLI Refactoring:** `main.py` will be overhauled to orchestrate the new commands. Context generation will become an implicitly called service.
-   **TUI:** The `ConsoleInteractorAdapter` will use `textual` for the interactive checklist, launching non-blocking editors for complex payload modifications.
-   **Validation:** A new `PlanValidator` service will validate plans against strict rules before user approval. Failures generate an immediate re-plan payload.
-   **State Management:** System-level side effects (like `READ` or `INVOKE`) will be implemented to correctly populate the *next* (`N+1`) turn's context directory.

## 4. Vertical Slices

- [x] **Slice 1: Foundation (Security, Config, LLM Client)**
    - Configure comprehensive security gates (`detect-secrets`, `bandit`, `pip-audit`). Add `litellm` dependency, implement `ConfigService` and `LiteLLMAdapter`, and wire them in `main.py`.
    - **Configurable Web Scraper:** Extend `WebScraperAdapter` to respect settings for precision, comments, and tables via the `ConfigService`.
- [x] **Slice 2: Auto-Initialization**
    - Automatically initialize `.teddy/config.yaml` and `.teddy/init.context` with default template content if they do not exist when the CLI is invoked.
- [x] **Slice 3: Refactor Execution Report Template**
    - Standardize the `execution_report.md.j2` template to provide a pruned, readable audit trail (replacing the legacy `is_concise` logic).
- [x] **Slice 4: Core Session & Context Engine**
    - Implement the backbone of the interactive session workflow.
    - Implement `SessionManager` and the basic `new`, `plan`, and `execute` commands.
    - Implement `ContextService` to build the `input.md` payload implicitly for the planning phase.
    - Implement stateful action side-effects for `execute` (e.g., updating `T_next/turn.context` for `READ`/`PRUNE`).
- [x] **Slice 5: Plan Validation & Self-Correction**
    - Integrate existing `PlanValidator` for the automatic feedback loop to enhance the core `execute` command with pre-flight checks.
    - Add additional checks for session workflow regarding files in context:
        - `EDIT`: Target file must be in current context.
        - `PRUNE`: Target file must be in current context.
        - `READ`: Target file must NOT be already in context (session or turn).
        - `INVOKE`: Check that agent to INVOKE exists.
- [x] **Slice 6: Interactive TUI & `resume` Workflow**
    - Implement the smart `resume` command and the `textual`-based TUI for interactive plan approval and editing.
- [x] **Slice 7: UX Polish & Bug Fixes (Session Lifecycle & Logging)**
    - **Core Bugs:** Fix `FileNotFoundError` in `session_service.py` when `turn.context` is missing.
    - **Lifecycle:** Rename `teddy new` to `teddy start`. Allow `start` to use a dynamic session name based on the first plan's H1. Update `resume` to accept an optional path argument (resolving a session folder, turn folder, or file) and auto-detect the active session if omitted.
    -   **Logging:** Suppress verbose LiteLLM logs. Generate an `input.md` in the turn directory containing the standardized project context. Save agent prompts using their actual names (e.g., `pathfinder.xml`) instead of `system_prompt.xml`.
    - **Config:** Add `--model`, `--provider`, and `--api-key` overrides to `teddy start`.
- [x] **Slice 8: TUI & UX Polish**
    - Wire `TextualPlanReviewer` to `IPlanReviewer` in `container.py`. Create a continuous interactive loop in the session orchestrator. Move planning logs to before the LLM call and add Turn N. Fix telemetry coloring and relax terminal action isolation.
- [x] **Slice 9: Advanced TUI & UX Polish**
    - Implement `input.md` standardized artifact, TUI instruction bridge, universal previewing, and enhanced diagnostic labels (AST/Diffs).
- [ ] **Slice 10: Agent Collaboration Model**
    - Implement `meta.yaml` ledgers, turn transition algorithms, and `INVOKE`/`RETURN` capabilities.
- [ ] **Slice 11: Automatic Session Log Generation**
    - Implement the `SessionLogGenerator` to compile session histories into a human-readable `session-log.md`, excluding turns that fail validation.

## 6. Technical Debt

### Structural & Security (Found during Deliverables)
- [ ] **Structural** - `textual_plan_reviewer_logic.py` exceeds file length limit (454/300). Logic should be split into thematic sub-modules (e.g., `context_logic.py`).
- [ ] **Complexity** - `_update_detail_view` exceeds complexity (13/9) and statement (56/40) limits. Needs decomposition into specialized preview handlers.
- [ ] **Refactor** - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py` exceeds 300 lines (currently 390 lines).
- [ ] **Refactor** - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py` exceeds 300 lines (367 lines). Move `_update_detail_view` or section builders to helpers.
- [ ] **Infrastructure Scopes:** Standardize all registrations in `src/teddy_executor/registries/infrastructure.py` to use `punq.Scope.transient` to ensure consistent test isolation and prevent singleton leaks (found during fix of `05-ci-preflight-failure`).
- [ ] **Refactor** - Update `ReviewerApp` to accept `IEditSimulator` via constructor injection instead of internal instantiation.
- [ ] **Structural** - Resolve Vulture unused variable hits in `ISessionManager` and `ISessionRepository` ports (requires whitelist update or alias).
- [ ] **Security** - Update `litellm` to 1.83.7+ and `pip` to resolve GHSA-xqmj-j6mv-4862 and GHSA-58qw-9mgm-455v.
- [ ] **Security** - Upgrade `litellm` to >= 1.83.7 to resolve GHSA-xqmj-j6mv-4862 (found during slice 00-07).
- [ ] **Linter** - Update `tests/harness/vulture_whitelist.py` to suppress unused argument noise in core ports.

### Code Quality (Linter & Logic)
- [ ] **File Length:** Refactor the following components to meet the 300-line limit:
    - [ ] `src/teddy_executor/adapters/outbound/console_interactor.py`
    - [ ] `src/teddy_executor/adapters/inbound/cli_helpers.py`
    - [ ] `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`
    - [ ] `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`
    - [ ] `src/teddy_executor/core/services/execution_orchestrator.py`
    - [ ] `src/teddy_executor/core/services/planning_service.py`
- [ ] **Complexity:** Refactor `check_action_logic` in `textual_plan_reviewer_logic.py` (PLR0911: 7 return statements).
- [ ] **Typing (Mypy):** Resolve union-attr and Worker awaitable mismatches in TUI components and `SessionOrchestrator` async methods.
- [x] **Static Analysis (Vulture):** Resolve remaining unused `args`/`kwargs` in `test_console_interactor.py` and `old_val` in `_apply_param_edit`.
- [ ] **Code Duplication (jscpd):** Resolve duplication across the codebase to meet the 0% threshold.
- [ ] **Magic Values (PLR2004):** Resolve remaining magic value warnings in `test_execution_orchestrator.py` and `test_planning_service_async.py`.

### Architectural & Harness Debt
- [x] **Quality Gate Reconciliation:** Resolve Vulture/Mypy friction in `vulture_whitelist.py` and core ports using a simplified "Import & Alias" strategy and global wildcards in `pyproject.toml`.
- [ ] **Harness Refactoring:** Transition `TEDDY_TEST_MOCK_EDITOR_OUTPUT` from an environment variable to a dedicated test adapter.
- [ ] **DI Isolation:** Improve isolation by resolving container locations dynamically instead of hardcoded module paths.
- [ ] **Test Pyramid Balance:** Resolve structural imbalance (Acceptance: 101, Integration: 101, Unit: 305) to satisfy 'Acceptance < Integration < Unit'.
- [ ] **Test Harness Resilience:** Refactor TUI test fixtures to use centralized DI (via `punq`) for mocks to prevent `TypeError` regressions.
- [ ] **Serialization Safety:** Replace `scrub_dict_for_serialization` with a schema-based approach (e.g., Pydantic) to prevent hangs from dynamic objects.
- [ ] **Domain Model Integrity:** Enforce strict primitive validation in domain models to prevent `MagicMock` leakage into state.

### TUI & UX Debt
- [ ] **External Tool Sync:** Generalize `code --wait` logic to handle other GUI editors that return before the file is released.
- [ ] **TUI Suspension:** Investigate `app.suspend()` instability in certain terminal environments during tool execution.
- [ ] **Logic Deduplication:** Refactor prefix-stripping regex `r"^\d{8}_\d{6}-"` and `_launch_editor` logic into shared utilities.
