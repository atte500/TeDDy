# MRE: SessionOrchestrator Finalization TypeError
- **Status:** Unresolved

## 1. Failure Context
Multiple tests across all levels fail when `SessionOrchestrator` attempts to trigger an automated re-plan due to a validation error.

## 2. Steps to Reproduce
Run the test suite:
```bash
poetry run pytest tests/suites/unit/core/services/test_session_orchestrator_validation.py
```

## 3. Expected vs. Actual Behavior
**Expected:** The orchestrator handles validation failures by finalizing the current turn and triggering a re-plan.
**Actual:** `TypeError: SessionOrchestrator._finalize_turn() got an unexpected keyword argument 'is_validation_failure'`

## 4. Relevant Code
- `src/teddy_executor/core/services/session_orchestrator.py`

## 5. Investigation Log
- **2026-03-27:** Initial report received via CI log.

## 6. Root Cause Analysis
The `SessionOrchestrator._trigger_replan` method was updated to pass `is_validation_failure=True` to `_finalize_turn`, but the latter's signature remains `(self, plan_path: str, report: ExecutionReport)`. This causes a `TypeError` whenever a logical or structural validation failure triggers a re-plan.

## 7. Implementation Notes
- Pending.
