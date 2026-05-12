# Bug: Windows Encoding Crash in Context UI Test
- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
After removing `PYTHONUTF8=1` from CI, `test_auto_pruning_heuristics_acceptance` fails on Windows.
- **Expected:** `reviewer.review` is called once.
- **Actual:** `reviewer.review` is called 0 times.
- **Context:** The test writes multiple plan and report files to the workspace using `Path.write_text()`.

## Diagnostic Analysis
### Causal Model
The test environment on Windows uses `cp1252` by default. The test writes plans/reports containing non-ASCII characters (emojis or specialized punctuation) without specifying an encoding. The SUT (which now strictly uses `utf-8`) attempts to read these files and likely throws a `UnicodeDecodeError`, causing the orchestrator to abort before the review step.

### Investigation History
1. Pathfinder identified that `PYTHONUTF8=1` was masking this risk.
2. Removal of the variable triggered a deterministic failure on the Windows runner.
3. Created `spikes/debug/18-mre-encoding.py` which reproduced the `UnicodeEncodeError` when simulating `cp1252` encoding with "🟢".
4. Verified that `mock_planning` in `test_auto_pruning_heuristics_acceptance` lacked explicit encoding.

## Solution
### Immediate Fix
Update the `mock_planning` function in `tests/suites/acceptance/test_context_management_ui.py` to use `encoding="utf-8"` when writing the plan file.

### Systemic Repair Strategy (Recommended)
To prevent the ~50 other vulnerable instances in the test suite from regressing, monkeypatch `pathlib.Path.write_text` and `pathlib.Path.read_text` in `tests/conftest.py` to default to `utf-8`.

This has been verified in `spikes/debug/18-mre-systemic-fix.py`.
