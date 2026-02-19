# LLM Client and Config Service

## 1. Goal (The "Why")

The goal is to establish core services for configuration management and LLM interaction. This initiative will decouple the application from specific LLM provider implementations and centralize all system settings, improving maintainability and extensibility. This work is the second part of the strategic initiative defined in [docs/project/specs/foundational-restructuring.md](../specs/foundational-restructuring.md).

## 2. Proposed Solution (The "What")

Based on the existing conventions in `docs/ARCHITECTURE.md`, we will implement two new core components following a port-and-adapter pattern.

1.  **Centralized Configuration Service (`ConfigService`)**
    -   **Responsibility:** A singleton service responsible for reading all system settings from a `.teddy/config.yaml` file.
    -   **Location:** `src/teddy_executor/core/services/config_service.py`
    -   **Contract:** It will provide a simple interface for retrieving configuration values, e.g., `get(key: str, default: Any = None) -> Any`.

2.  **LLM Client Abstraction (`ILlmClient` and `LiteLLMAdapter`)**
    -   **Port (`ILlmClient`):** An interface defining the contract for LLM interactions.
        -   **Location:** `src/teddy_executor/core/ports/outbound/llm_client.py`
        -   **Contract:** Based on the workflow in `docs/project/specs/interactive-session-workflow.md`, it will have a primary method: `generate_plan(system_prompt: str, context_payload: str, user_instruction: str) -> str`.
    -   **Adapter (`LiteLLMAdapter`):** The concrete implementation of the `ILlmClient` port.
        -   **Location:** `src/teddy_executor/adapters/outbound/litellm_adapter.py`
        -   **Technology:** It will use the `litellm` library to communicate with various LLM APIs.
        -   **Dependencies:** It will depend on the `ConfigService` to retrieve API keys, model names, and other LLM-related settings.

## 3. Implementation Analysis (The "How")

These new components are designed to be isolated and easily testable. The primary integration point with the existing application will be in the composition root (`src/teddy_executor/main.py`), where the `LiteLLMAdapter` will be instantiated and injected where the `ILlmClient` port is required.

The `litellm` library will be added as a new project dependency in the root `pyproject.toml`.

## 4. Vertical Slices

This brief will be implemented as a single vertical slice with the following ordered tasks:

-   [ ] **Task: Add Dependency**
    -   Add `litellm` to the project's dependencies in the root `pyproject.toml`.

-   [ ] **Task: Implement ConfigService**
    -   Create `src/teddy_executor/core/services/config_service.py`.
    -   Implement the logic to read and parse `.teddy/config.yaml`.
    -   Add unit tests for the `ConfigService`.

-   [ ] **Task: Define LLM Port**
    -   Create the `ILlmClient` interface in `src/teddy_executor/core/ports/outbound/llm_client.py` with the `generate_plan` method.

-   [ ] **Task: Implement LiteLLMAdapter**
    -   Create `src/teddy_executor/adapters/outbound/litellm_adapter.py`.
    -   Implement the `ILlmClient` interface.
    -   Inject and use the `ConfigService` to retrieve LLM settings (e.g., model, api_key).
    -   Write integration tests for the `LiteLLMAdapter` that mock the external API call.

-   [ ] **Task: Wire Dependencies**
    -   In the composition root (likely `src/teddy_executor/main.py`), register the `ConfigService` and wire the `LiteLLMAdapter` to the `ILlmClient` port using `punq`.

-   [ ] **Task: Verify Integration**
    -   Ensure the full test suite passes after the new services are integrated.
