# Component Design: TestEnvironment
- **Status:** Implemented
- **Source:** [`tests/harness/setup/test_environment.py`](/tests/harness/setup/test_environment.py)

## Purpose
The setup component of the Test Harness Triad. It builds an isolated DI container with happy-path port mocks, swaps the global container so the CLI uses it, and manages the lifecycle of a temporary workspace.

## Consumers
- [`Test Composition`](./composition.md): The `env` and `real_env` fixtures wrap a `TestEnvironment`.
- Acceptance and integration test suites: Resolve services, override mocks, and drive the CLI through this harness.

## Dependencies
- **`create_container`** ([Composition Root](/src/teddy_executor/container.py)): Builds the fresh DI container.
- **`RealAdapterMixin`** (`tests.harness.setup.real_adapter_mixin`): Adds the `with_real_*` registration helpers. This module has no component doc yet.
- **`register_mock`** (`tests.harness.setup.mocking`): Creates and registers an auto-specced port mock.

## Class Invariants
- `explicit_setup_required`: `get_service` and the `_container` property raise `RuntimeError` before `setup` runs.
- `global_container_swap`: `_deep_swap_container` patches `teddy_executor.container._container`, `get_container`, and `teddy_executor.__main__.get_container`.
- `managed_workspace_cleanup`: A harness-created workspace under the system temp directory is removed in `teardown`.
- `happy_path_defaults`: Each registered port mock receives contract-faithful defaults, so an unconfigured test still runs a green path.
- `deterministic_tty_default`: The `ISystemEnvironment` double reports `isatty() == False` unless `with_tty` overrides it.

## Inbound Ports
None — this is a test harness component.

## Outbound Ports
None — this is a test harness component.

## Data Contracts
- **`workspace`** (`Optional[Path]`): The isolated working directory.
- **`container`** (`Optional[punq.Container]`): The test-configured DI container.

## Operations

### `TestEnvironment(monkeypatch, workspace=None)`
- **Postconditions:** Stores the monkeypatch handle and marks the workspace as managed when none is supplied.

### `setup() -> TestEnvironment`
- **Postconditions:** Creates a managed temp workspace when needed, builds the container, registers the default mocks, swaps the global container, and anchors real adapters only for an explicitly supplied workspace.

### `mock_port(port_type) -> Any`
- **Postconditions:** Registers an auto-specced mock for `port_type`, applies its happy-path defaults, and returns it.

### `get_service(service_type) -> Any`
- **Preconditions:** `setup` has run.
- **Postconditions:** Resolves the service from the test container.
- **Exceptions:** `RuntimeError` when `setup` has not run.

### `with_tty(value=True) -> TestEnvironment`
- **Postconditions:** Sets the `ISystemEnvironment` double's `isatty()` return value and returns `self`.

### `create_batch_files(base_path, count, prefix="file") -> None`
- **Postconditions:** Creates `count` empty files under `base_path` using low-level OS calls.

### `without_reviewer() -> TestEnvironment`
- **Postconditions:** Registers a null `IPlanReviewer` and re-registers the orchestrator without a reviewer.

### `teardown() -> None`
- **Postconditions:** Removes a managed workspace. Monkeypatches are restored by the pytest fixture.

### Internal helpers
`_register_default_mocks` composes the system, UI, AI, and I/O mock groups. `_apply_mock_defaults` dispatches to the per-port default handlers. `_deep_swap_container` forces the global container singleton.
