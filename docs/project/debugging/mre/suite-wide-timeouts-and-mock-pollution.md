- **Status:** Unresolved
- **Target Agent:** Debugger

## 1. Failure Context
After implementing lazy loading for `litellm` in `LiteLLMAdapter` and `PlanningService`, and introducing a global `litellm` mock in `tests/conftest.py`, the entire test suite (unit, integration, and acceptance) began timing out or hanging.

## 2. Steps to Reproduce
Run the unit test suite:
```shell
pytest tests/unit -n auto
```

## 3. Expected vs. Actual Behavior
- **Expected:** Tests pass in < 5 seconds.
- **Actual:** Suite hangs or times out after 30-180 seconds. Multiple `AttributeError` (e.g., `'bool' object has no attribute 'called'`) and `TypeError` (serialization errors) occur before the timeout.

## 4. Relevant Code
- [src/teddy_executor/core/services/planning_service.py](/src/teddy_executor/core/services/planning_service.py): Suspected infinite recursion/hang in `yaml.dump` when processing `meta` containing `MagicMock` objects.
- [tests/conftest.py](/tests/conftest.py): Global `litellm` mock implementation.
- [src/teddy_executor/adapters/outbound/litellm_adapter.py](/src/teddy_executor/adapters/outbound/litellm_adapter.py): Lazy loading logic.
- [tests/unit/adapters/outbound/test_litellm_adapter.py](/tests/unit/adapters/outbound/test_litellm_adapter.py): Tests failing due to mock attribute pollution (boolean assignment to `set_verbose`).

## 5. Hypothesis
1. **Mock Serialization Hang:** `PlanningService` attempts to dump `meta` to YAML. During unit tests, `response.model` or `turn_cost` are `MagicMock` objects. `yaml.dump` enters infinite recursion or extreme slowness when traversing these objects.
2. **Mock Pollution:** The global `litellm` mock is shared across tests. Assignment like `litellm.set_verbose = False` in the adapter replaces the Mock attribute with a literal boolean, causing subsequent tests to fail when checking `.called`.
