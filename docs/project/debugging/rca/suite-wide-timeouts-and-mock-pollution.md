- **Status:** Resolved
- **MRE:** [docs/project/debugging/mre/suite-wide-timeouts-and-mock-pollution.md](/docs/project/debugging/mre/suite-wide-timeouts-and-mock-pollution.md)

## 1. Summary
After the introduction of lazy loading for the `litellm` library and a global mock in `tests/conftest.py`, the entire test suite began hanging or timing out. Multiple `AttributeError` were also observed. The root cause was a combination of exponential mock recursion during YAML operations and attribute pollution of shared global mocks.

## 2. Investigation Summary
- **Hypothesis 1 (Mock Serialization Hang):** Verified. `yaml.safe_load()` attempts to process `MagicMock` objects returned by `file_system_manager.read_file()` as streams, triggering recursive attribute lookups (`__len__`, `__iadd__`) that cause `unittest.mock` to hang.
- **Hypothesis 2 (Mock Pollution):** Verified. Literal assignments in `LiteLLMAdapter` (e.g., `litellm.set_verbose = False`) replace Mock attributes with booleans in the shared global `mock_litellm`.
- **Secondary Finding:** An `UnboundLocalError` in `test_litellm_adapter.py` was caused by a shadowed import of `MagicMock`.

## 3. Root Cause
- **Technical Cause:** Lack of defensive type casting when passing dynamic content to `yaml.safe_load`. In unit tests, these inputs are often `MagicMock` objects which `PyYAML` cannot safely handle as stream inputs.
- **Systemic Cause:** The use of a module-level global mock in `tests/conftest.py` without a robust, automated reset fixture leads to cross-test state leakage.

## 4. Verified Solution
- **Defensive Casting:** Every call to `yaml.safe_load(content)` must be wrapped in `yaml.safe_load(str(content))` to ensure `MagicMock` objects are treated as plain strings (e.g., `"<MagicMock ...>"`), which is valid YAML, rather than recursive streams.
- **Mock Isolation:** Update the `reset_litellm_mock` fixture to explicitly restore attributes replaced by assignments.
- **Serialization Scrub:** Ensure all metadata values are primitive types (str, int, float, bool) and not Mocks before calling `yaml.dump`.

```python
# Core fix mechanic:
meta = yaml.safe_load(str(meta_content)) or {}
```

## 5. Preventative Measures
- **Type Safety in Services:** Avoid passing raw results from `IFileSystemManager` directly to parsers without explicit casting or validation.
- **Mock Configuration:** Prefer `spec=...` when creating global mocks to prevent accidental attribute creation and pollution.

## 6. Recommended Regression Test
A new unit test should be added to `test_planning_service.py` that explicitly passes a `MagicMock` to `generate_plan` for both the `user_message` and filesystem responses, asserting that the method completes within < 1 second.
