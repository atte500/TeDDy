**Status:** Implemented
**Introduced in:** [Slice 10: Foundation (Security, Config, LLM Client)](/docs/project/slices/10-foundation-security-config-llm.md)

## 1. Purpose / Responsibility

The `YamlConfigAdapter` is responsible for reading application configuration from a YAML file (`.teddy/config.yaml`) and making it available to the application. It provides a concrete implementation for the `IConfigService` port.

## 2. Ports

-   **Type:** Outbound Adapter
-   **Implements:** `IConfigService`

## 3. Implementation Details / Logic

-   **Configuration Schema:**
    -   **`similarity_threshold`**: (Optional) A float between 0.0 and 1.0 defining the global default for fuzzy `EDIT` matching. Defaults to `0.95`.
-   The adapter will look for the configuration file at a fixed path: `.teddy/config.yaml` relative to the project root.
-   It will parse the YAML file upon first access and cache the contents in memory to prevent redundant file I/O operations for the lifetime of the application instance.
-   **Nested Key Support:** The adapter supports dot-notation for retrieving nested configuration keys (e.g., `execution.default_timeout_seconds`).
-   If the configuration file does not exist, it will behave as if it were an empty configuration, returning default values or `None` for all requests. It will not raise an error.
-   It will use the `PyYAML` library for parsing.

## 4. Data Contracts / Methods

This adapter implements the methods defined in the `IConfigService` port contract. See `docs/architecture/core/ports/outbound/config_service.md`.
