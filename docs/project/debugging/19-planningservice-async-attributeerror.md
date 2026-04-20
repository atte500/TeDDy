# Bug: PlanningService Async AttributeError

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-05-planning-lifecycle-visibility](/docs/project/slices/00-05-planning-lifecycle-visibility.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md)

## Symptoms

### Error Message
```text
AttributeError: 'str' object has no attribute 'get'
File "src/teddy_executor/core/services/planning_service.py", line 89, in async_generate_plan
    agent_name = meta.get("agent_name", "pathfinder")
```

### Context
During the migration of `PlanningService` to async, the implementation of `async_generate_plan` was introduced. A unit test `test_planning_service_has_async_generate_plan_seam` in `tests/suites/unit/core/services/test_planning_service_async.py` triggers this error.

The error occurs because `yaml.safe_load(str(meta_content))` is returning a string instead of a dictionary. This suggests that `meta_content` (read from `meta.yaml`) is either empty, contains a simple string, or `yaml.safe_load` is behaving unexpectedly with the provided input.

### Minimal Reproduction
Run the following unit test:
```shell
pytest tests/suites/unit/core/services/test_planning_service_async.py
```

## Context & Scope

### Regressing Delta
The bug was introduced in the newly implemented `async_generate_plan` method in `src/teddy_executor/core/services/planning_service.py` during the async migration. Specifically, the logic for loading `meta.yaml` does not verify that the parsed YAML is a dictionary.

### Environmental Triggers
- Use of unconfigured `Mock` objects for `IFileSystemManager` in tests.
- Presence of a `meta.yaml` file (or a truthy `path_exists` mock) where the content is not a valid YAML dictionary.

### Ruled Out
- `LLMClient` and `ContextService` are unrelated to this specific failure, as the error occurs during metadata loading before those services are fully utilized for generation.

## Diagnostic Analysis

### Causal Model
1. `async_generate_plan` checks if `meta.yaml` exists using `file_system_manager.path_exists`.
2. In the unit test, `file_system_manager` is a raw `Mock()`, so `path_exists` returns a `MagicMock` object, which evaluates to `True`.
3. The service calls `file_system_manager.read_file()`, which also returns a `MagicMock`.
4. The service converts this mock to a string: `str(meta_content)`, resulting in a string like `"<MagicMock name='mock.read_file()' ...>"`.
5. `yaml.safe_load()` parses this string. Since it's not valid YAML structure but is a valid string, it returns the string itself.
6. `meta` is now a `str` object.
7. `meta.get("agent_name", "pathfinder")` is called. Since `str` has no `get` method, an `AttributeError` is raised.

### Discrepancies
- **Observation:** `meta` is a string instead of a dictionary.
- **Resolution:** `yaml.safe_load` returns a string if the input string does not contain YAML key-value pairs or other structures. (resolved: added defensive check to ensure `meta` is an instance of `dict`)

### Investigation History
- **Attempt 1:** Reproduced via `pytest tests/suites/unit/core/services/test_planning_service_async.py`. Confirmed `AttributeError` at line 89.
- **Attempt 2:** Applied defensive `isinstance(meta, dict)` check. Discovered test-only regression due to `AsyncMock` returning awaitables for sync methods.
- **Attempt 3:** Refactored unit test to use `MagicMock` with selective `AsyncMock` assignment. Verified fix and test pass.

## Solution

### Implemented Fixes
- Added `isinstance(meta, dict)` check in `PlanningService.async_generate_plan` and `PlanningService.generate_plan` after `yaml.safe_load`. This ensures that malformed or mocked YAML content (like the string representation of a `MagicMock`) does not crash the service.
- Refactored `test_planning_service_has_async_generate_plan_seam` to correctly mock the `ILlmClient` contract, ensuring synchronous methods return primitives and asynchronous methods are awaitable.

### Prevention
- The updated unit test now serves as a regression test for both the structural requirement of `ProjectContext` and the mixed sync/async nature of the LLM client.
- The defensive check in the service layer prevents similar crashes when encountering uninitialized or malformed metadata on the filesystem.
