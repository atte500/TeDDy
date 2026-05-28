# Slice: Fix Windows CI Worker Crashes via CI-Specific Timeout Headroom
- **Status:** Planned
- **Milestone:** [N/A]
- **Specs:** [N/A]

## Business Goal
Eliminate intermittent CI failures on Windows to ensure reliable quality gates and reduce developer friction.

## Scenarios
> As a Developer, I want the CI to provide enough headroom for heavy tests on slow runners so that I don't encounter false-positive worker crashes.
```gherkin
Given a CI environment (CI=true)
And a test suite with heavy TUI components
When the tests are executed on a Windows runner under contention
Then the timeout should automatically scale to provide 30s of headroom
And the worker process should not be terminated prematurely
```

## Deliverables
- [ ] **Harness** - Implement `pytest_collection_modifyitems` in `tests/conftest.py` for dynamic timeout scaling.
- [ ] **Cleanup** - Delete debug spikes and shadow files.

## Implementation Plan
1. Add `pytest_collection_modifyitems` hook to `tests/conftest.py`.
2. Verify that local tests still fail if they exceed 5s (default).
3. Verify via remote probe that the full suite passes on Windows.
