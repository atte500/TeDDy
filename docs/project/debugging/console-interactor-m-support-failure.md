# MRE: Console Interactor 'm' Support Failure
- **Status:** Resolved

## 1. Failure Context
The unit test `test_confirm_action_supports_m_for_message` in `tests/suites/unit/adapters/outbound/test_console_interactor_m_support.py` fails on macOS and Windows runners in GitHub Actions. It passes on Ubuntu runners and on the developer's local macOS machine.

## 2. Steps to Reproduce
1. Run `pytest tests/suites/unit/adapters/outbound/test_console_interactor_m_support.py` in a macOS or Windows environment similar to GHA.

## 3. Expected vs. Actual Behavior
- **Expected:** The `message` returned by `confirm_action` should be `"New user instruction"` (as mocked).
- **Actual:** The `message` returned is `"modified content"`.

## 4. Relevant Code
- `src/teddy_executor/adapters/outbound/console_interactor.py`
- `tests/suites/unit/adapters/outbound/test_console_interactor_m_support.py`

## 5. Investigation Log
- [2026-03-30] Initial triage. Noticed the unexpected string `'modified content'`. Found that `TEDDY_TEST_MOCK_EDITOR_OUTPUT` is used as a testing hook in `ConsoleInteractorAdapter`.
- [2026-03-30] Spike `spikes/debug/repro_env_leak.py` confirmed that `TEDDY_TEST_MOCK_EDITOR_OUTPUT` overrides the `open` mock.
- [2026-03-30] Identified that several tests in `test_reviewer_app_modifications.py` and `test_textual_plan_reviewer.py` set this variable but do not clear it.

## 6. Root Cause Analysis
- **Root Cause:** Environment variable leakage. The `TEDDY_TEST_MOCK_EDITOR_OUTPUT` variable, used to mock external editor output for TUI tests, was being set in some unit tests without being cleared in a `finally` block or via a proper `pytest` fixture (e.g., `monkeypatch.setenv`).
- **Trigger:** When running tests in parallel (`pytest -n auto`), if a test that sets the variable runs before `test_confirm_action_supports_m_for_message` in the same process, the latter fails because the testing hook takes precedence over the manual `open()` mock.

## 7. Implementation Notes
- **Strategy 1: Global Cleanup (Defense in Depth)**
  - Add an `autouse` fixture to `tests/conftest.py` that clears `TEDDY_TEST_MOCK_EDITOR_OUTPUT` before and after every test.
- **Strategy 2: Test Hardening**
  - Refactor `test_reviewer_app_modifications.py` and `test_textual_plan_reviewer.py` to use `monkeypatch.setenv()` instead of direct `os.environ` manipulation.
  - Update `test_confirm_action_supports_m_for_message.py` to explicitly clear the variable using `monkeypatch.delenv(..., raising=False)` to ensure it's not affected by environment state.
