# Milestone 09: Interactive Session Workflow & LLM Integration

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
    - Modify the `execution_report.md.j2` template to correctly generate "Session Report" and "CLI Report" formats based on an `is_concise` flag.
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
- [ ] **Slice 9: Advanced TUI & UX Polish**
    - Implement `input.md` standardized artifact, TUI instruction bridge, universal previewing, and enhanced diagnostic labels (AST/Diffs).
- [ ] **Slice 10: Agent Collaboration Model**
    - Implement `meta.yaml` ledgers, turn transition algorithms, and `INVOKE`/`RETURN` capabilities.
- [ ] **Slice 11: Automatic Session Log Generation**
    - Implement the `SessionLogGenerator` to compile session histories into a human-readable `session-log.md`, excluding turns that fail validation.

## 6. Technical Debt
### Code Quality
- [ ] **File Length:** Refactor oversized files to adhere to the 300-line limit:
    - `src/teddy_executor/core/services/markdown_plan_parser.py` (304 lines)
    - `src/teddy_executor/core/services/session_orchestrator.py` (319 lines)
    - `src/teddy_executor/adapters/outbound/console_interactor.py`
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer.py`
    - `src/teddy_executor/adapters/inbound/cli_helpers.py`
- [ ] **ReviewerApp Mypy/Vulture:** Resolve incompatible override and unused `mode` variable in `push_screen_wait` in `textual_plan_reviewer.py`.
- [ ] **Code Duplication (jscpd):** Resolve code duplication across multiple files to meet the 0% threshold.
- [ ] **Dead Code (Vulture):** Resolve all dead code warnings, investigating potential false positives in ports.
- [ ] **Duplicated Logic:** Refactor `ReviewerApp._launch_editor` in `textual_plan_reviewer.py` to use a central editor/diffing utility.

### Architectural Debt
- [x] **Windows CI Stability:** Fixed "Not properly terminated" worker crashes caused by CWD state leakage in integration tests.
- [x] **TUI Asynchronous Deadlocks:** The production `textual_plan_reviewer.py` currently uses a custom, flawed `asyncio.Future` based `push_screen_wait` implementation that causes deadlocks during modal interactions. This MUST be refactored to use Textual's native `await app.push_screen_wait()` along with `@work` decorators on action handlers, mirroring the verified fixes in the `tui_deferred_harvest` prototype.
- [ ] **Test Pyramid Violation:** Resolve the structural imbalance (Acceptance: 101, Integration: 101, Unit: 305) to satisfy the 'Acceptance < Integration < Unit' rule.
- [ ] **File Length (TUI Refactor):** Refactor `console_interactor.py` and `cli_helpers.py` to meet 300-line limit.
- [ ] **Pygments Vulnerability:** Update `pygments` to 2.20.0+ to resolve GHSA-5239-wwwm-4pmq.
- [ ] **DI & Test Harness:**
    - Refactor the `TEDDY_TEST_MOCK_EDITOR_OUTPUT` hook to use a dedicated test adapter instead of an environment variable.
    - Improve DI isolation by resolving container locations dynamically instead of using hardcoded module paths.
- [ ] **Serialization Safety:** Replace `scrub_dict_for_serialization` with a schema-based approach (e.g., Pydantic) to prevent serialization hangs.
- [ ] **Domain Model Validation:** Enforce strict primitive validation in domain models to prevent `MagicMock` leakage.
- [ ] **Documentation:** Reconcile `ARCHITECTURE.md` setup descriptions with the fixture-based pattern in `composition.py`.
- [ ] **Test Harness Fragility:** Refactor TUI test fixtures to use centralized dependency injection (via `punq`) for mocks to avoid systemic `TypeError` regressions when constructor signatures change.

### Security
- [ ] **Bandit:** Resolve `subprocess` security warning in `system_environment_inspector.py`.
- [ ] **Dependency:** Update `aiohttp` to 3.13.4+, `litellm` to 1.83.0+, and `pygments` to 2.20.0+ to resolve multiple vulnerabilities found by `pip-audit`.

### New Technical Debt (Discovered during TUI Refinement)
- [ ] **File Length:** Refactor `src/teddy_executor/core/services/execution_orchestrator.py` (329 lines).
- [ ] **File Length:** Refactor `src/teddy_executor/core/services/session_orchestrator.py` (414 lines).
- [ ] **Complexity:** Refactor `ExecutionOrchestrator.execute` (C901, PLR0912, PLR0915).
- [ ] **File Length (TUI Adapters):** Refactor TUI adapter components to satisfy the 300-line limit:
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py`
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_logic.py`
    - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py`
- [ ] **ActionLog Parameters:** Audit other services (beyond `ActionExecutor`) for potential parameter loss when creating `ActionLog` objects from `ActionData`.
- [ ] **ShellAdapter Maintenance:** Refactor `ShellAdapter` (>300 lines, C901, PLR0915) after terminal reset sanitization additions. Also fix `Mypy` bytes vs str errors in `_run_subprocess`.
- [ ] **TUI Suspension:** Investigate `app.suspend()` instability in certain terminal environments during external tool execution.
- [ ] **Editor Sync:** Generalize the `code --wait` logic to handle other GUI editors that return before the file is released.
- [ ] **File Length:** Refactor `src/teddy_executor/adapters/outbound/console_interactor.py` (>300 lines).
- [ ] **File Length:** Refactor `src/teddy_executor/adapters/inbound/cli_helpers.py` (>300 lines).
- [ ] **File Length:** Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py` (>300 lines).
- [ ] **File Length:** Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py` (455 lines).
- [ ] **Complexity:** Refactor `check_action_logic` (PLR0911: 7 return statements).
- [ ] **Complexity:** Refactor `ExecutionOrchestrator.execute` (C901, PLR0912, PLR0915).
- [ ] **Complexity:** Refactor `PlanningService.generate_plan` and `PlanningService.async_generate_plan` (C901, PLR0915).
- [ ] **File Length:** Refactor `ExecutionOrchestrator.py` to meet 300-line limit (currently 327 lines).
- [ ] **File Length:** Refactor `src/teddy_executor/core/services/planning_service.py` (336 lines).
- [ ] **Linter (Tests):** Resolve magic value warning (PLR2004) in `test_planning_service_async.py`.
- [ ] **Typing:** Resolve `Mypy` union-attr errors and `Worker` awaitable mismatch in TUI logic/app.
- [ ] **Vulture:** Configure `.vulture_whitelist` or pragmas for abstract Port definitions to resolve 40+ false positives.
- [ ] **Vulture (Console Interactor Tests):** Resolve unused `args`/`kwargs` in `test_console_interactor.py`.
- [ ] **Vulture:** Resolve unused `old_val` in `_apply_param_edit`.
- [ ] **Linter (Tests):** Clean up unused `mock_preview` (F841) in `test_tui_regressions.py` and fix module-level import (E402) in `test_shell_adapter_timeout.py`.
- [ ] **Duplicated Logic:** Refactor prefix-stripping regex `r"^\d{8}_\d{6}-"` into a shared utility (e.g., `SessionRepository` or a string util) to avoid duplication across `PlanningService`, `SessionPlanner`, and `SessionRepository`.
- [ ] **File Length:** Refactor `src/teddy_executor/core/services/planning_service.py` (351 lines).
- [ ] **Complexity:** Refactor `PlanningService.async_generate_plan` and `generate_plan` (C901, PLR0915).
- [ ] **Typing:** Resolve Mypy type mismatches in `SessionOrchestrator` async methods (`run_sync` argument types and `Plan | None` handling).
- [ ] **Magic Values:** Remove magic values from `test_execution_orchestrator.py` and `test_planning_service_async.py` (PLR2004).
