# MRE: Cascading Context and Newline Regressions

- **Status:** Resolved

## Failure Context
After implementing registration guards in `__main__.py`, two distinct regressions appeared:
1. `test_teddy_context_aggregates_cascading_context`: Reports `--- FILE NOT FOUND ---` for files created in the temporary workspace.
2. `test_edit_newline_mismatch.py`: `EDIT` validation fails with score below 0.95.

## Steps to Reproduce
1. `pytest tests/suites/integration/core/services/test_session_orchestration_integration.py::test_teddy_context_aggregates_cascading_context`
2. `pytest tests/suites/acceptance/test_edit_newline_mismatch.py`

## Expected vs. Actual Behavior
### Context Failure
- **Expected:** `content_a` and `content_b` are present in the context report.
- **Actual:** `--- FILE NOT FOUND ---` printed for both.

### Newline Mismatch
- **Expected:** `SUCCESS` (Score >= 0.95).
- **Actual:** `Validation Failed`.

## Relevant Code
- `src/teddy_executor/__main__.py`
- `src/teddy_executor/container.py`
- `tests/conftest.py`
- `src/teddy_executor/core/services/context_service.py`
- `src/teddy_executor/core/services/plan_validator.py`

## Investigation Log
> **Hypothesis**: The registration guard in `__main__.py` prevents correct re-anchoring of adapters when `runner.invoke` is used sequentially in the same process (xdist worker).
