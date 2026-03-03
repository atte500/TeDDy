# Slice 27: Standardize Test Infrastructure

## Business Goal
Eradicate repetitive DI registration boilerplate and rebalance the test pyramid to ensure a maintainable, high-performance test suite.

## Acceptance Criteria
- **Centralized Mocking:** All common ports are available as shared fixtures in `tests/conftest.py` and automatically registered in the `container`.
- **Boilerplate Eradication:** All manual `container.register` calls are removed from the identified test files.
- **Pyramid Alignment:** Low-level validation edge cases are moved from acceptance tests to unit tests.

## Scope of Work

### 1. Centralize fixtures in `tests/conftest.py`
Implement the following fixtures to handle automatic container registration:
- `mock_user_interactor` (spec=`IUserInteractor`)
- `mock_fs` (spec=`IFileSystemManager`)
- `mock_env` (spec=`ISystemEnvironment`)
- `mock_shell` (spec=`IShellExecutor`)
- `mock_scraper` (spec=`IWebScraper`)
- `mock_searcher` (spec=`IWebSearcher`)
- `mock_tree_gen` (spec=`IRepoTreeGenerator`)

### 2. Refactor Unit & Integration Layer
Remove manual registration and local mock fixtures in the 10 files identified in [Test Infrastructure Standards](../specs/test-infrastructure-standards.md).

### 3. Logic Migration (Pyramid Rebalancing)
Move validation logic to `tests/unit/core/services/test_plan_validator.py` from:
- `tests/acceptance/test_critical_bug_fixes.py` (Parser nesting and execute syntax)
- `tests/acceptance/test_create_file_action.py` (File already exists error)
- `tests/acceptance/test_edit_action.py` (File not found error)
- `tests/acceptance/test_report_enhancements.py` (Smart fencing validation)

### 4. Acceptance Layer Cleanup
Standardize DI usage using the new shared fixtures in the 5 acceptance tests identified in the specification.
