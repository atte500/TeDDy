# Test Context: TestEnvironment
- **Status:** Implemented

## 1. Purpose / Responsibility
The `TestEnvironment` encapsulates the complex setup required for atomic, isolated acceptance and integration tests. It manages the lifecycle of the DI container, temporary filesystems, and monkeypatching.

## 2. Ports
- **Primary Driving Adapter:** Provides a unified interface for tests to interact with the environment.
- **Secondary Driven Port:** Orchestrates `pytest`, `punq`, and `pyfakefs` (or similar).

## 3. Implementation Details / Logic
- **Container Isolation:** Ensures every test gets a fresh `punq.Container` with all outbound ports (Filesystem, Shell, LLM) mocked by default.
- **Fluent Registry:** Allows tests to override specific mocks using a fluent API (e.g., `env.with_mock_llm(response="...").run(...)`).

## 4. Data Contracts / Methods
- `setup() -> None`: Initializes the fresh container and patches `teddy_executor.__main__`.
- `get_service(type: T) -> T`: Retrieves a service from the test-configured container.
- `teardown() -> None`: Cleans up monkeypatches and resets global state.
