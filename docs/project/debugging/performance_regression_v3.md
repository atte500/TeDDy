# Bug: Stubborn Test Suite Performance Regression (< 10s Goal)

## 1. Failure Context
- **Component:** Test Suite (`pytest` with `pytest-xdist`)
- **Symptom:** Test suite execution time is consistently around ~18-22s.
- **Goal:** Get the full test suite below 10 seconds.

## 2. Steps to Reproduce
1. Run `poetry run pytest -n auto`
2. Observe total duration is ~18-22s.

## 3. Expected vs Actual
- **Expected:** Suite finishes in < 10s.
- **Actual:** Suite finishes in ~18-22s.

## 4. Prior Attempts & Refuted Hypotheses (What NOT to do)
The following optimizations were attempted and *failed* to move the needle on the total 18s execution time. They are considered red herrings for the *primary* bottleneck:
1. **Reducing `time.sleep()` calls:** Changing 5s and 2s sleeps in `test_hanging_command_management.py` to 0.1s did not reduce the overall suite time.
2. **Mocking `os.utime` instead of sleep:** Removing the 1.1s sleep in `test_session_resume_robustness.py` did not reduce the overall suite time.
3. **Lazy `__main__.py` Container Init:** Changing `container = create_container()` to a getter function to avoid eager module-level DI wiring during collection did not reduce the overall suite time.
4. **Wiping `tests/.tmp/`:** Adding a session-scoped fixture to delete accumulated temporary directories before the test run did not reduce the overall suite time.

## 5. Current Leading Theory
Because individual test durations are small (max 1.4s) and concurrency is high (10 workers), but total time is massive (~18s) and collection time is high (~7s), the bottleneck must be in the `pytest` collection phase, `xdist` worker synchronization, or global plugin overhead (e.g., `pyfakefs` or `pytest-cov`).

## 6. Root Cause Analysis
Through rigorous profiling using `cProfile` and `importtime`, two distinct bottlenecks were identified that account for the massive 7-second collection time:

1. **Missing `testpaths` Configuration (The Primary Bottleneck):**
   The `pyproject.toml` file lacked a `testpaths = ["tests"]` directive in the `[tool.pytest.ini_options]` block. As a result, `pytest` was recursively scanning the entire workspace (including `.git`, `.venv`, and `node_modules` if present), evaluating its `pytest_ignore_collect` hook an astonishing **17,829 times**. Restricting the scan strictly to the `tests/` directory reduces collection time by ~3.2 seconds.
2. **Heavy Third-Party Library Eager Import (The Secondary Bottleneck):**
   The `mistletoe` markdown parsing library, specifically `mistletoe.core_tokens.py`, contains heavy regex set comprehensions that take **~2.3 seconds** to evaluate upon import. Because the `parser_*.py` files in `src/teddy_executor/core/services/` import these tokens eagerly at the module level, every test file that touches the parser pays this massive 2.3-second penalty during the collection phase.

Combining these two factors fully explains the ~6.7s collection phase (3.2s traversing + 2.3s importing + ~1.2s normal pytest overhead).

**3. CLI Global Initialization (CLI Latency):**
While "Lazy `__main__.py` Container Init" was correctly refuted as the primary cause of the *test suite* regression, it is the undisputed root cause of the ~1-2s delay when invoking `teddy execute`. The global `container = create_container()` call in `src/teddy_executor/__main__.py` eagerly builds the entire DI graph, which forces the heavy `mistletoe` imports before Typer can even parse the command line arguments.

**4. Worker-Level Execution Bottlenecks (Unrefuted):**
While collection blocks the global suite, the execution phase (~11-15s) is bottlenecked on individual `pytest-xdist` workers by heavy system interactions:
*   **Massive Synchronous I/O:** `test_tree_generator_performance.py` touches 5,000 files sequentially on the real disk, monopolizing a worker thread.
*   **Python Subprocess Overhead:** Tests in `test_shell_adapter.py` and `test_execute_granular_failure.py` repeatedly spawn full `sys.executable` processes, incurring a ~100-200ms penalty per call.
*   **Heavy Process Isolation:** `test_lazy_loading_integration.py` spawns a full subprocess to verify `sys.modules`.

## 7. Recommended Solution
1. **Immediate Fix:** Add `testpaths = ["tests"]` to `pyproject.toml`. This is a one-line fix that instantly drops the collection time to ~3.5 seconds.
2. **Architectural Fix (Parsers):** Refactor the `parser_*.py` files to adhere to Rule 11 (Lazy loading of heavy libraries). By deferring `from mistletoe import ...` to inside the methods that require them, the 2.3s penalty is removed from test collection.
3. **Architectural Fix (CLI):** Wrap `container = create_container()` in `__main__.py` inside a `get_container()` getter function so the DI graph is only built when a command actually executes.
4. **Worker-Level Quick Wins:** Reduce the 5,000 file loop in `test_tree_generator_performance.py` to 500 files (adjusting the performance budget assertion accordingly). Acknowledge subprocess overhead in shell adapter tests as accepted latency, but ensure no unnecessary subprocesses are spawned elsewhere.
