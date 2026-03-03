# Slice 24: Standardize Test Infrastructure & Pivot Strategy

## Business Goal
To ensure high-quality, maintainable tests by eradicating manual dependency injection boilerplate and aligning the testing strategy with the Traditional Testing Pyramid.

## Acceptance Criteria
- [ ] **DI Standardization:** All test files using manual container patching or instantiation are refactored to use the `container` fixture.
- [ ] **Pyramid Alignment (Migration):** Unit tests currently in `tests/acceptance/` are moved to `tests/unit/`.
- [ ] **Pyramid Alignment (Pruning):** Redundant formatting assertions in acceptance tests are replaced by focused unit tests in the service layer.
- [ ] All tests pass successfully after refactoring.

## Scope of Work

### 1. Test Migration (Pyramid Alignment)
The following files are unit tests currently sitting in the acceptance folder. Move them to the unit layer to improve speed and isolation:
- `tests/acceptance/test_plan_builder.py` -> `tests/unit/test_plan_builder.py`
- `tests/acceptance/test_helpers.py` -> `tests/unit/core/test_report_parsing_helpers.py`

In `tests/acceptance/test_markdown_plans.py`, `tests/acceptance/test_report_enhancements.py`, and `tests/acceptance/test_context_command_refactor.py`:
- Prune granular formatting checks (e.g., verifying smart fencing, dynamic language tags, or specific H3 headers).
- Ensure these formatting details are covered in `tests/unit/core/services/test_markdown_report_formatter.py` or `tests/unit/core/services/test_context_service.py`.
- Retain only the high-level orchestration verification in the acceptance layer.

### 2. Dependency Injection Refactoring
Refactor the following files to use the `container` fixture from `tests/conftest.py` and remove manual patching/instantiation:
- `tests/acceptance/test_generalized_clipboard_output.py`
- `tests/acceptance/test_prompt_action.py`
- `tests/acceptance/test_interactive_execution.py`
- `tests/acceptance/test_change_preview_feature.py`

**Standard Pattern to use:**
```python
# The 'container' fixture automatically patches teddy_executor.__main__.container
def test_feature(container, monkeypatch):
    # Register mocks if needed via the provided container instance
    container.register(IMyPort, instance=Mock())
    # Run CLI
    ...
```
