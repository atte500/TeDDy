# Architectural Brief: Project Restructuring & Foundations

## 1. Goal (The "Why")

The strategic goal is to flatten the project structure and establish core, foundational services in preparation for the new interactive session workflow. This is the foundational first step that unblocks all subsequent feature development by creating a clean, stable, and ergonomic codebase.

This work must be completed before any other new features (like the Markdown Parser or Interactive Workflow) are implemented to avoid significant rework and ensure all new code is built in the correct, final location.

## 2. Referenced Specifications
-   [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md)

## 3. Proposed Solution (The "What")

This initiative involves two main activities:
1.  **Repository Flattening:** The legacy `packages/executor` structure will be removed, and all core source code will be moved to the project root. This simplifies the development workflow, dependency management, and CI/CD scripts.
2.  **Core Service Implementation:** New, foundational services for configuration (`ConfigService`) and LLM interaction (`ILlmClient`) will be created. These services provide stable interfaces that the rest of the new features will depend on.

## 4. Vertical Slices

This brief will be implemented as a single, comprehensive vertical slice.

-   **[ ] Task: Restructure Repository:**
    -   Move all contents of `packages/executor/` to the project root.
    -   Delete the obsolete `packages/tui/` directory.
    -   Update all imports, `pyproject.toml`, and CI scripts to reflect the new structure.
-   **[ ] Task: Implement `ConfigService`:**
    -   Create a service to read settings from `.teddy/config.yaml` as the primary source, falling back to environment variables. This will manage settings like `TEDDY_DIFF_TOOL` and `open_after_action`.
-   **[ ] Task: Implement `ILlmClient` Port:**
    -   Add `litellm` as a dependency.
    -   Define an `ILlmClient` outbound port.
    -   Create a `LiteLLMAdapter` that implements the port.
    -   Wire up the adapter in the `main.py` composition root.
