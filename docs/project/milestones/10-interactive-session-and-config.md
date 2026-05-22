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
- [ ] Fix `ExecutionOrchestrator.resume` signature mismatch with `IRunPlanUseCase`.
- [ ] `PlanningService.generate_plan` complexity (10/9) and statement count (44/40) exceeds limits following session loop repair. Requires extraction of goal resolution and metadata management into sub-services.

### Structural & Complexity (SLOC / PLR)
- [ ] **SLOC Limit Enforcement:** Refactor core components to meet the 300-line limit:
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py` (~450 lines)
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py` (~350 lines)
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`
    - `src/teddy_executor/adapters/inbound/cli_helpers.py`
    - `src/teddy_executor/adapters/outbound/console_interactor.py`
    - `src/teddy_executor/core/services/execution_orchestrator.py`
    - `src/teddy_executor/core/services/planning_service.py`
- [ ] **Complexity Reductions:**
    - Decompose `_update_detail_view` in `textual_plan_reviewer_logic.py` (Complexity 13/9).
    - Refactor `check_action_logic` in `textual_plan_reviewer_logic.py` (PLR0911: 7 return statements).
- [ ] **Boundary Fragmentation:** Resolve architectural "fragmentation debt" where logic (TUI, Sessions, Action Parser) has been split into 6-8 files solely to bypass SLOC limits, introducing circular dependency hacks via local imports. Move toward higher-level abstractions (Controllers/State Machines).

### Security & Dependencies
- [ ] **Security Updates:** Update `litellm` (1.83.7+) and `pip` to resolve critical vulnerabilities (GHSA-xqmj-j6mv-4862, GHSA-58qw-9mgm-455v).

### Test Harness & Infrastructure
- [ ] **Harness Refactoring:**
    - Support a clean `interactive_mode` toggle in `TestEnvironment` instead of manual `without_reviewer()` re-wiring.
    - Transition `TEDDY_TEST_MOCK_EDITOR_OUTPUT` from an environment variable to a dedicated test adapter.
    - Refactor TUI test fixtures to use centralized DI (via `punq`) for mocks to prevent `TypeError` regressions.
- [ ] **DI Isolation:** Standardize all registrations in `infrastructure.py` to use `punq.Scope.transient` and resolve container locations dynamically.
- [ ] **Test Pyramid Balance:** Resolve structural imbalance (Acceptance/Integration count exceeds Unit in some layers) to satisfy the 'Acceptance < Integration < Unit' rule.
- [ ] **Banned Mocks:** Resolve `TID251` (MagicMock/patch) violations in `tests/suites/unit/adapters/inbound/test_textual_plan_reviewer_logic.py`.
- [ ] Resolve `TID251` (MagicMock) violations in `tests/suites/unit/core/services/test_session_orchestrator_pruning.py`.

### Code Quality & Standards
- [ ] **Typing:** Resolve Mypy union-attr and Worker awaitable mismatches in TUI components and `SessionOrchestrator` async methods.
- [ ] **Static Analysis:**
    - Resolve duplication across the codebase (jscpd 0% threshold).
    - Resolve remaining PLR2004 magic value warnings in test suites.
- [ ] **Data Integrity:**
    - Replace `scrub_dict_for_serialization` with a schema-based approach (e.g., Pydantic) to prevent hangs from dynamic objects.
    - Enforce strict primitive validation in domain models to prevent `MagicMock` leakage into system state.
    - Several components print emojis directly without ensuring UTF-8 support at the code level.

### TUI & UX Debt
- [ ] **External Tools:** Generalize `code --wait` logic to handle other GUI editors and investigate `app.suspend()` instability in restricted terminal environments.
- [ ] **Logic Deduplication:** Refactor timestamp prefix-stripping regex and `_launch_editor` logic into shared utilities.
