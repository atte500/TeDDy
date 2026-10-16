# Component Design: Test Composition
- **Status:** Implemented
- **Source:** [`tests/harness/setup/composition.py`](/tests/harness/setup/composition.py)

## Purpose
The composition root of the test suite. It installs a global `litellm` mock, re-exports the shared port mocks, and provides the pytest fixtures that every test uses for a fresh DI container and an isolated workspace.

## Consumers
- The full test suite: Consumes the `container`, `env`, `real_env`, `tee_log_path`, `installed_tee`, `openrouter_mock`, and `temp_cache_dir` fixtures.

## Dependencies
- [`TestEnvironment`](./test_environment.md): Builds the managed workspace and container used by the `env` and `real_env` fixtures.
- **`tests.harness.setup.mocks`** (`teddy_executor` test harness): Supplies the re-exported port-mock fixtures. This module has no component doc yet.
- **`pytest`** (external): Provides the fixture decorator, `monkeypatch`, and `httpserver`.

## Class Invariants
- `litellm_mocked_before_import`: `sys.modules["litellm"]` is replaced with a configured `Mock` at module load, so the heavy import never runs during the suite.
- `safe_default_completion`: The global `litellm.completion` double returns a minimal valid plan, so an unconfigured LLM call never crashes a test.
- `killpg_poka_yoke`: The autouse `guard_os_killpg` fixture blocks `os.killpg` on a non-integer or protected process-group id.
- `fresh_container_per_test`: The `container` fixture builds a new container and patches the global singleton.

## Inbound Ports
None — this is a test harness component.

## Outbound Ports
None — this is a test harness component.

## Data Contracts
- **`env`** (fixture): A `TestEnvironment` with mocked ports.
- **`real_env`** (fixture): A `TestEnvironment` with a real filesystem, shell, and init service.
- **`container`** (fixture): A fresh `punq.Container` bound to the CLI entry point.

## Operations

### Fixtures
`guard_os_killpg` blocks dangerous `os.killpg` calls. `tee_log_path` yields a temporary log path. `installed_tee` installs and tears down a `Tee`. `container` builds and patches a fresh container. `env` yields a mocked `TestEnvironment`. `real_env` yields a real-adapter `TestEnvironment`. `openrouter_mock` configures the `httpserver` with the OpenRouter model payload. `temp_cache_dir` yields a temporary update-cache directory.

### `is_tee_active() -> bool`
- **Postconditions:** Returns `True` when `sys.stderr` is a `_TeeWriter` proxy, meaning the `Tee` context is installed.

### `_default_completion_mock`
- **Postconditions:** Supplies a completion whose message content is a minimal valid plan, so tests that trigger an unconfigured LLM call observe a parseable plan.
