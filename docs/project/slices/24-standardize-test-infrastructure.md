# Slice 24: Standardize Test Infrastructure & Pivot Strategy

## Business Goal
To ensure high-quality, maintainable tests by eradicating manual dependency injection boilerplate and aligning the testing strategy with the Traditional Testing Pyramid.

## Acceptance Criteria
- [x] **DI Standardization:** All test files using manual container patching or instantiation are refactored to use the `container` fixture.
- [x] **Pyramid Alignment (Migration):** Unit tests currently in `tests/acceptance/` are moved to `tests/unit/`.
- [x] **Pyramid Alignment (Pruning):** Redundant formatting assertions in acceptance tests are replaced by focused unit tests in the service layer.
- [x] All tests pass successfully after refactoring.

## Implementation Summary

### Work Completed
- **Test Layer Migration:**
    - Moved `tests/acceptance/test_plan_builder.py` to `tests/unit/test_plan_builder.py`.
    - Moved and renamed `tests/acceptance/test_helpers.py` to `tests/unit/core/test_report_parsing_helpers.py`.
    - Resolved import discrepancies resulting from the move.
- **Granular Assertion Pruning:**
    - Audited acceptance tests for redundant output formatting checks (smart fencing, dynamic language tags, section headers).
    - Enhanced `tests/unit/core/services/test_markdown_report_formatter.py` with 14 focused test cases to provide robust service-level coverage of these details.
    - Pruned redundant checks from `tests/acceptance/test_report_enhancements.py` and `tests/acceptance/test_context_command_refactor.py`, leaving them focused on high-level orchestration.
- **DI Infrastructure Standardization:**
    - Eradicated manual container instantiation and patching in four major acceptance test files: `test_generalized_clipboard_output.py`, `test_prompt_action.py`, `test_interactive_execution.py`, and `test_change_preview_feature.py`.
    - Adopted the centralized `container` fixture from `tests/conftest.py` across all refactored files, ensuring consistent isolation and reducing boilerplate.

### Significant Refactoring
- The transition from manual patching to the `container` fixture simplified the test functions and clarified dependencies by using explicit `container.register(...)` calls for mocks.
- The unit layer now serves as the primary validator for the visual/structural aspects of Markdown reports, significantly decreasing the fragility of the acceptance suite.

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
