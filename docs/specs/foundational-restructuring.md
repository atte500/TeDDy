# Specification: Foundational Restructuring

## 1. Strategic Goal (The "Why")

The primary goal is to refactor the project's foundational structure to improve developer experience, simplify maintenance, and establish core services. This is a strategic prerequisite that unblocks all subsequent feature development—including the Markdown parser and the new interactive session workflow—by creating a clean, stable, and ergonomic codebase.

## 2. Problem Statement

The current project structure presents several challenges that hinder efficient development:

-   **High Cognitive Overhead:** The nested `packages/executor` structure adds unnecessary complexity to file navigation, import paths, and dependency management.
-   **Scattered Configuration:** Configuration logic (e.g., for `TEDDY_DIFF_TOOL`) is not centralized, making it difficult to manage and extend system settings.
-   **Missing Core Abstractions:** There is no standardized interface for interacting with LLMs, which will lead to duplicated effort and inconsistent implementations in future features.

## 3. Scope

### In Scope
-   Flattening the repository by moving all source code from `packages/executor/` to the project root.
-   Updating all necessary configurations (`pyproject.toml`, CI scripts, import paths) to support the new structure.
-   Creating a new `ConfigService` responsible for loading settings from a configuration file and environment variables.
-   Defining a new `ILlmClient` port (interface) and implementing a `LiteLLMAdapter` as the default implementation for LLM communication.

### Out of Scope
-   Implementation of any features that *use* these new services (e.g., the interactive session workflow).
-   Changes to the TUI package, which is slated for removal.

## 4. Success Criteria

This initiative will be considered complete when:
-   All source code resides in a root-level `src/` directory (or similar flat structure).
-   The `packages/` directory has been completely removed.
-   All tests pass successfully in the new flattened structure.
-   The `ConfigService` is implemented and can load configuration from a file.
-   The `ILlmClient` port and its `LiteLLMAdapter` are defined and integrated into the application's composition root.
