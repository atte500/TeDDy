# Test Context: Test Composition
- **Status:** Implemented

## 1. Purpose / Responsibility
The `Test Composition` component acts as the "Composition Root" for the testing suite. Its primary responsibility is to ensure absolute test isolation by providing a fresh Dependency Injection (DI) container for every test and managing global mocks for heavy or side-effect-prone external libraries.

## 2. Ports
- **Primary Driving Adapter:** Drives the `Core` services by injecting mocks/stubs into the `container`.
- **Secondary Driven Port:** Uses `pytest` fixtures and `monkeypatch` to isolate the system environment.

## 3. Implementation Details / Logic
- **Global Mocking (Performance):** To maintain the "Inner Loop" speed, heavy libraries (like `litellm`) are mocked at the `sys.modules` level before any tests run. This prevents expensive imports (1.2s+) from occurring multiple times or at all during the suite.
- **Container Isolation:** The `container` fixture creates a fresh `punq.Container` for each test. Crucially, it uses `monkeypatch` to replace the global container instance in `teddy_executor.__main__`, ensuring that the CLI entry point uses the test-configured services.
- **Transient Registration:** All services are registered with `punq.Scope.transient` to prevent state leakage between individual service resolutions within a single test run.

## 4. Data Contracts / Methods
- `container(monkeypatch)`: A pytest fixture that returns a fresh, patched DI container.
- `mock_[port_name](container)`: A suite of specialized fixtures (e.g., `mock_fs`, `mock_shell`) that register a `unittest.mock.Mock` for a specific outbound port and return the mock object for assertion.
