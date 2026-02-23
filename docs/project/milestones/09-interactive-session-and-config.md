# Milestone 09: Interactive Session Workflow & LLM Integration

## 1. Goal (The "Why")

This milestone represents a major strategic evolution for TeDDy. It combines establishing core, decoupled services for configuration and LLM interaction with the implementation of a seamless, local-first, CLI-driven interactive session workflow. The goal is to realize the "Obsidian for AI coding" philosophy by managing stateful, multi-turn AI collaboration directly on the filesystem.

-   **Referenced Specifications:**
    -   [Foundational Restructuring](../specs/foundational-restructuring.md)
    -   [Interactive Session Workflow](../specs/interactive-session-workflow.md)
    -   [Context Payload Format](../specs/context-payload-format.md)
    -   [Report Format](../specs/report-format.md)

## 2. Proposed Solution (The "What")

1.  **Config & LLM Foundation:**
    -   A singleton `ConfigService` reading from `.teddy/config.yaml`.
    -   An `ILlmClient` port with a `LiteLLMAdapter` implementation using the `litellm` library.
2.  **Session Manager:** A service handling all stateful filesystem interactions (creating turn directories, managing session artifacts).
3.  **Context-Centric Workflow:** An implicitly generated `input.md` file serving as the AI's complete worldview for each turn.
4.  **Refactored CLI:** New session-aware commands (`new`, `resume`, `plan`, `execute`, `context`), with a smart `resume` orchestrator.
5.  **Interactive TUI:** A multi-layered approval workflow using `textual`, featuring "Context-Aware Editing" to preview/modify AI actions inline.
6.  **Plan Validation & Auto Re-planning:** Comprehensive pre-flight validation catching errors (e.g., `FIND` blocks) and automatically triggering a self-correction AI loop.
7.  **Agent Collaboration & Ledger:** Supporting multi-agent sub-routines via `INVOKE`/`RETURN`, tracked by a `meta.yaml` ledger and a comprehensive `session-log.md`.

## 3. Implementation Guidelines (The "How")

-   **Integration:** The `LiteLLMAdapter` and `ConfigService` will be instantiated in the `main.py` composition root.
-   **CLI Refactoring:** `main.py` will be overhauled to orchestrate the new commands. Context generation will become an implicitly called service.
-   **TUI:** The `ConsoleInteractorAdapter` will use `textual` for the interactive checklist, launching non-blocking editors for complex payload modifications.
-   **Validation:** A new `PlanValidator` service will validate plans against strict rules before user approval. Failures generate an immediate re-plan payload.
-   **State Management:** System-level side effects (like `READ` or `INVOKE`) will be implemented to correctly populate the *next* (`N+1`) turn's context directory.

## 4. Vertical Slices

- [ ] **Slice 1: Implement Config Service and LLM Client**
    - Add `litellm` dependency, implement `ConfigService` and `LiteLLMAdapter`, and wire them in `main.py`.
- [ ] **Slice 2: Session Scaffolding & Core Commands**
    - Implement `SessionManager` and the basic `new`, `plan`, and `execute` commands.
- [ ] **Slice 3: Context-Centric Workflow**
    - Implement `ContextService` to build the `input.md` payload implicitly for the planning phase.
- [ ] **Slice 4: Core Workflow & Enhanced Interactivity**
    - Implement the smart `resume` loop and the `textual`-based TUI with in-terminal/non-blocking editors.
- [ ] **Slice 5: Plan Validation & Automated Re-planning**
    - Implement the `PlanValidator` and the automatic feedback loop upon validation failure.
- [ ] **Slice 6: Action Side-Effects & Reporting**
    - Implement action timings, forward-looking side-effects (e.g., for `READ`), and rich markdown reporting.
- [ ] **Slice 7: Agent Collaboration Model**
    - Implement `meta.yaml` ledgers, turn transition algorithms, and `INVOKE`/`RETURN` capabilities.
- [ ] **Slice 8: Automatic Session Log Generation**
    - Implement the `SessionLogGenerator` to compile session histories into a human-readable `session-log.md`.
